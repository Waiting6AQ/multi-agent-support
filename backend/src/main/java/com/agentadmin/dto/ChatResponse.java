package com.agentadmin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;

/** Java 网关返回给前端的聊天响应 */
@Data
@AllArgsConstructor
public class ChatResponse {

    /** 会话ID（数据库主键），前端下次对话带上它继续 */
    @JsonProperty("session_id")
    private Long sessionId;

    private String reply;
    private String intent;
    private double confidence;
    private boolean escalated;
}
