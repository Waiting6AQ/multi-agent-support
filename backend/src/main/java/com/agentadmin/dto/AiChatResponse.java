package com.agentadmin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * agent_engine（Python）返回的响应体
 * Python 字段为 snake_case，用 @JsonProperty 映射
 */
@Data
public class AiChatResponse {

    @JsonProperty("conversation_id")
    private String conversationId;

    private String reply;

    private String intent;

    private Double confidence;

    @JsonProperty("quality_score")
    private Double qualityScore;

    private Boolean escalated;

    @JsonProperty("escalation_reason")
    private String escalationReason;
}
