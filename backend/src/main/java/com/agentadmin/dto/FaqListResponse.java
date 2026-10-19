package com.agentadmin.dto;

import lombok.Data;

import java.util.List;

/** FAQ 列表响应 */
@Data
public class FaqListResponse {

    private long total;
    private List<FaqInfo> faqs;
}
