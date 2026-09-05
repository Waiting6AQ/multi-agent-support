package com.agentadmin.service;

import com.agentadmin.common.BusinessException;
import com.agentadmin.dto.AiChatResponse;
import com.agentadmin.dto.ChatRequest;
import com.agentadmin.dto.ChatResponse;
import com.agentadmin.model.ChatSession;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * 聊天服务：Java 网关转发 agent_engine（AI 服务）+ 业务侧自持记录
 *
 * 链路：校验/建会话 → 转发 AI（带 X-User-Id）→ 落库（user + assistant 消息）→ 标题更新
 * 降级：AI 服务不可达/超时 → SSE error 事件 + 友好提示，不落库
 *
 * 流式采用【原样透传】：Python 的 SSE 字节流逐行搬给前端（格式 100% 保留），
 * 只劫持 done 事件（附加 session_id）和旁路解析 token（落库用）。
 * StreamingResponseBody 由 Spring 自动异步调用（请求线程释放），无需手动线程池。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {

    private final SessionService sessionService;
    private final ChatRecordService recordService;
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    @Value("${app.ai-service-url}")
    private String aiServiceUrl;

    public ChatResponse chat(Long userId, ChatRequest req) {
        // 1. 定位会话：带了 session_id 校验归属，没带自动创建
        ChatSession session = resolveSession(userId, req);

        // 2. 转发 AI 服务（超时/降级在方法内处理）
        AiChatResponse ai = callAiService(userId, session, req.getMessage());

        // 3. 事务落库：用户消息 + AI 回答（带意图标签）+ 标题更新（ChatRecordService，原子性）
        recordService.saveExchange(session, req.getMessage(), ai.getReply(), ai.getIntent());

        return new ChatResponse(
                session.getId(),
                ai.getReply(),
                ai.getIntent(),
                ai.getConfidence() != null ? ai.getConfidence() : 0.0,
                Boolean.TRUE.equals(ai.getEscalated())
        );
    }

    /** 会话解析：带会话ID（数据库主键）必须属于当前用户；否则新建 */
    private ChatSession resolveSession(Long userId, ChatRequest req) {
        if (req.getSessionId() != null) {
            return sessionService.getOwnedSession(userId, req.getSessionId());
        }
        return sessionService.create(userId);
    }

    /** 非流式转发 AI：POST {ai-url}/api/v1/chat，注入 X-User-Id 可信头（预留数据隔离/审计） */
    private AiChatResponse callAiService(Long userId, ChatSession session, String message) {
        try {
            return restClient.post()
                    .uri(aiServiceUrl + "/api/v1/chat")
                    .header("X-User-Id", String.valueOf(userId))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of(
                            "message", message,
                            "conversation_id", session.getConversationId()))
                    .retrieve()
                    .body(AiChatResponse.class);
        } catch (ResourceAccessException e) {
            log.warn("AI 服务不可达或超时: {}", e.getMessage());
            throw new BusinessException(503, "AI 服务暂时不可用，请稍后再试");
        } catch (Exception e) {
            log.error("调用 AI 服务失败", e);
            throw new BusinessException(503, "AI 服务暂时不可用，请稍后再试");
        }
    }

    /**
     * 流式聊天：原样透传 agent_engine 的 SSE 流（打字机效果）
     * StreamingResponseBody：Spring 自动在异步线程调用 writeTo，请求线程立即释放
     */
    public StreamingResponseBody chatStream(Long userId, ChatRequest req) {
        ChatSession session = resolveSession(userId, req);
        return outputStream -> relayStream(outputStream, userId, session, req.getMessage());
    }

    /**
     * 行级原样透传（具体分支逻辑见 relayLines）：Python 的 SSE 格式 100% 保留给前端，
     * 转发期间旁路记录落库所需元数据（token 拼接完整回复、intent 意图），不干扰转发
     */
    private void relayStream(OutputStream outputStream, Long userId, ChatSession session, String userMsg) {
        // 标题只依赖提问：流开始前先落库，前端收到 done 刷新列表时必然是新标题（消除竞态）
        recordService.updateTitleEarly(session, userMsg);
        StringBuilder fullReply = new StringBuilder();
        String intent = null;
        try {
            String json = objectMapper.writeValueAsString(Map.of(
                    "message", userMsg,
                    "conversation_id", session.getConversationId()));
            // exchange 的回调返回值即 exchange 的返回值——intent 在方法内赋值，无 lambda 闭包问题
            intent = restClient.post()
                    .uri(aiServiceUrl + "/api/v1/chat/stream")
                    .header("X-User-Id", String.valueOf(userId))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(json)
                    .exchange((request, response) -> {
                        if (!response.getStatusCode().is2xxSuccessful()) {
                            throw new RuntimeException("AI 服务返回 HTTP " + response.getStatusCode().value());
                        }
                        return relayLines(outputStream, response.getBody(), session, fullReply);
                    });
        } catch (Exception e) {
            log.error("SSE 透传失败", e);
            writeError(outputStream);
            return;
        }
        // 流正常结束：事务落库（user + assistant 消息 + 意图标签 + 标题更新）
        recordService.saveExchange(session, userMsg, fullReply.toString(), intent);
    }

    /** 逐行透传，返回 intent（intent 事件里旁路提取，早于 done 更可靠）；token 旁路拼进 fullReply */
    private String relayLines(OutputStream outputStream, InputStream in, ChatSession session, StringBuilder fullReply) {
        String intent = null;
        String pendingEvent = null;   // 当前正在组装的事件名（event 行已到、data 行待配对）
        try {
            BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isEmpty()) {
                    outputStream.write("\n".getBytes(StandardCharsets.UTF_8));   // 事件分隔
                    pendingEvent = null;                                          // 事件结束
                } else if (line.startsWith("event:")) {
                    pendingEvent = line.substring(6).trim();
                    writeLine(outputStream, line);
                } else if (line.startsWith("data:")) {
                    String data = line.substring(5).trim();
                    if ("intent".equals(pendingEvent)) {
                        // intent 事件（回答之前必到）：旁路提取 intent（落库用）——不等 done，
                        // 长流程可能被超时掐断（done 到不了），但 intent 此时已可得
                        @SuppressWarnings("unchecked")
                        Map<String, Object> intentData = objectMapper.readValue(data, Map.class);
                        Object it = intentData.get("intent");
                        intent = it != null ? String.valueOf(it) : null;
                        writeLine(outputStream, line);
                    } else if ("done".equals(pendingEvent)) {
                        // 劫持 done：附加 session_id（前端继续对话用）
                        @SuppressWarnings("unchecked")
                        Map<String, Object> done = objectMapper.readValue(data, Map.class);
                        done.put("session_id", session.getId());
                        writeLine(outputStream, "data: " + objectMapper.writeValueAsString(done));
                    } else if (pendingEvent == null) {
                        // 裸 data = token 事件：原样写，同时旁路拼一份完整回复（落库用）
                        @SuppressWarnings("unchecked")
                        Map<String, Object> tokenData = objectMapper.readValue(data, Map.class);
                        fullReply.append(String.valueOf(tokenData.getOrDefault("token", "")));
                        writeLine(outputStream, line);
                    } else {
                        writeLine(outputStream, line);
                    }
                } else {
                    writeLine(outputStream, line);
                }
                outputStream.flush();   // 每行 flush 保证实时到达（打字机效果）
            }
        } catch (Exception e) {
            log.error("SSE 流读取/转发失败", e);
        }
        return intent;
    }

    private void writeLine(OutputStream outputStream, String line) throws Exception {
        outputStream.write((line + "\n").getBytes(StandardCharsets.UTF_8));
    }

    /** AI 服务不可达：向客户端发 error 事件（前端显示友好提示） */
    private void writeError(OutputStream outputStream) {
        try {
            writeLine(outputStream, "event: error");
            writeLine(outputStream, "data: AI 服务暂时不可用，请稍后再试");
            outputStream.write("\n".getBytes(StandardCharsets.UTF_8));
            outputStream.flush();
        } catch (Exception ignored) {
            // 客户端可能已断开
        }
    }

}
