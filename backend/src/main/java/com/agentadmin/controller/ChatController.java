package com.agentadmin.controller;

import com.agentadmin.common.Result;
import com.agentadmin.config.JwtInterceptor;
import com.agentadmin.dto.ChatRequest;
import com.agentadmin.dto.ChatResponse;
import com.agentadmin.service.ChatService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    /** 聊天：转发 agent_engine，落库，返回 AI 回复 */
    @PostMapping
    public Result<ChatResponse> chat(HttpServletRequest request,
                                     @Valid @RequestBody ChatRequest req) {
        Long userId = (Long) request.getAttribute(JwtInterceptor.ATTR_USER_ID);
        return Result.ok(chatService.chat(userId, req));
    }

    /** 流式聊天：原样透传 Python SSE 流（打字机效果），流结束后落库 */
    @PostMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public StreamingResponseBody stream(HttpServletRequest request, HttpServletResponse response,
                                        @Valid @RequestBody ChatRequest req) {
        // 提示反向代理（Nginx 等）不要缓冲该响应，保证 token 实时到达
        response.setHeader("X-Accel-Buffering", "no");
        Long userId = (Long) request.getAttribute(JwtInterceptor.ATTR_USER_ID);
        return chatService.chatStream(userId, req);
    }
}
