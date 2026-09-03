package com.agentadmin.model;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ChatMessage {
    private Long id;
    private Long sessionId;
    /** user（用户提问） / assistant（AI 回答） */
    private String role;
    private String content;
    /** AI 意图标签（仅 assistant 消息有值）：tech_support/order_service/product_consult/chitchat/web_search/escalate */
    private String intent;
    private LocalDateTime createdAt;
}
