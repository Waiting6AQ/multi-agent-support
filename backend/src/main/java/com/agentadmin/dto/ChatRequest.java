package com.agentadmin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ChatRequest {

    @NotBlank(message = "消息不能为空")
    private String message;

    /** 会话ID（数据库主键，来自 /api/sessions 列表）；不传则自动创建新会话 */
    @JsonProperty("session_id")
    private Long sessionId;
}
