package com.agentadmin.service;

import com.agentadmin.mapper.ChatMessageMapper;
import com.agentadmin.mapper.ChatSessionMapper;
import com.agentadmin.model.ChatMessage;
import com.agentadmin.model.ChatSession;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

/**
 * ChatRecordService 单元测试：一轮问答的落库内容与标题规则
 */
class ChatRecordServiceTest {

    private ChatSessionMapper sessionMapper;
    private ChatMessageMapper messageMapper;
    private ChatRecordService recordService;

    @BeforeEach
    void setUp() {
        sessionMapper = mock(ChatSessionMapper.class);
        messageMapper = mock(ChatMessageMapper.class);
        recordService = new ChatRecordService(sessionMapper, messageMapper);
    }

    private ChatSession session() {
        ChatSession s = new ChatSession();
        s.setId(1L);
        s.setTitle("新会话");
        return s;
    }

    @Test
    @DisplayName("落库内容：user 消息（无意图）+ assistant 消息（带意图标签）")
    void savesBothMessages() {
        recordService.saveExchange(session(), "帮我查订单 ORD001", "已为您查询到订单", "order_service");

        ArgumentCaptor<ChatMessage> captor = ArgumentCaptor.forClass(ChatMessage.class);
        verify(messageMapper, times(2)).insert(captor.capture());
        List<ChatMessage> saved = captor.getAllValues();

        assertThat(saved.get(0).getRole()).isEqualTo("user");
        assertThat(saved.get(0).getContent()).isEqualTo("帮我查订单 ORD001");
        assertThat(saved.get(0).getIntent()).isNull();
        assertThat(saved.get(0).getSessionId()).isEqualTo(1L);

        assertThat(saved.get(1).getRole()).isEqualTo("assistant");
        assertThat(saved.get(1).getContent()).isEqualTo("已为您查询到订单");
        assertThat(saved.get(1).getIntent()).isEqualTo("order_service");
    }

    @Test
    @DisplayName("标题规则：每轮更新为最新提问，超过 80 字截断")
    void titleFollowsLatestQuestionAndIsTruncated() {
        String longQuestion = "问".repeat(100);

        recordService.saveExchange(session(), longQuestion, "回答", null);

        verify(sessionMapper).updateTitle(eq(1L), argThat((String t) -> t.length() == 80));
    }

    @Test
    @DisplayName("标题规则：短提问原样作为标题")
    void titleKeepsShortQuestion() {
        recordService.saveExchange(session(), "你好", "您好", "chitchat");

        verify(sessionMapper).updateTitle(1L, "你好");
    }
}
