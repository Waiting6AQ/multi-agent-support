package com.agentadmin.dto;

import lombok.Data;

/** 一条 FAQ（来自 agent_engine FAQ 管理接口） */
@Data
public class FaqInfo {

    private Integer id;
    private String question;
    private String answer;
    private String category;
}
