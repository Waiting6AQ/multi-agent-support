package com.agentadmin.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/** 新增 / 修改 FAQ 的请求体 */
@Data
public class FaqRequest {

    @NotBlank(message = "问题不能为空")
    private String question;

    @NotBlank(message = "答案不能为空")
    private String answer;

    /** 不填时由服务层补默认分类 */
    private String category;
}
