package com.agentadmin.service;

import com.agentadmin.common.BusinessException;
import com.agentadmin.dto.FaqInfo;
import com.agentadmin.dto.FaqListResponse;
import com.agentadmin.dto.FaqRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

/**
 * FAQ 管理：调 agent_engine 的 FAQ 接口
 *
 * 权限由 Controller 上的 @RequireAdmin 把关，这层只负责转发和错误透传。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FaqService {

    private static final String DEFAULT_CATEGORY = "常见问题";

    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    @Value("${app.ai-service-url}")
    private String aiServiceUrl;

    /** 列表（不分页：FAQ 数据量小） */
    public FaqListResponse list() {
        try {
            return restClient.get()
                    .uri(aiServiceUrl + "/api/v1/faqs/")
                    .retrieve()
                    .body(FaqListResponse.class);
        } catch (RestClientResponseException e) {
            throw passThrough(e);
        } catch (ResourceAccessException e) {
            throw unavailable(e);
        }
    }

    /** 新增，返回带 id 的完整记录；问题重复由引擎返回 409 */
    public FaqInfo create(FaqRequest req) {
        try {
            return restClient.post()
                    .uri(aiServiceUrl + "/api/v1/faqs/")
                    .body(toBody(req))
                    .retrieve()
                    .body(FaqInfo.class);
        } catch (RestClientResponseException e) {
            throw passThrough(e);
        } catch (ResourceAccessException e) {
            throw unavailable(e);
        }
    }

    /** 修改；id 不存在由引擎返回 404 */
    public FaqInfo update(int id, FaqRequest req) {
        try {
            return restClient.put()
                    .uri(aiServiceUrl + "/api/v1/faqs/" + id)
                    .body(toBody(req))
                    .retrieve()
                    .body(FaqInfo.class);
        } catch (RestClientResponseException e) {
            throw passThrough(e);
        } catch (ResourceAccessException e) {
            throw unavailable(e);
        }
    }

    /** 删除；id 不存在由引擎返回 404 */
    public void delete(int id) {
        try {
            restClient.delete()
                    .uri(aiServiceUrl + "/api/v1/faqs/" + id)
                    .retrieve()
                    .toBodilessEntity();
        } catch (RestClientResponseException e) {
            throw passThrough(e);
        } catch (ResourceAccessException e) {
            throw unavailable(e);
        }
    }

    /** 转发体：分类留空时补默认值，免得引擎那边返回 422 */
    private FaqRequest toBody(FaqRequest req) {
        FaqRequest body = new FaqRequest();
        body.setQuestion(req.getQuestion());
        body.setAnswer(req.getAnswer());
        body.setCategory(req.getCategory() == null || req.getCategory().isBlank()
                ? DEFAULT_CATEGORY : req.getCategory());
        return body;
    }

    /** 引擎的错误语义原样透传（409 问题重复 / 404 不存在 / 422 参数问题） */
    private BusinessException passThrough(RestClientResponseException e) {
        String detail = extractDetail(e);
        log.warn("FAQ 接口返回 {}: {}", e.getStatusCode().value(), detail);
        return new BusinessException(e.getStatusCode().value(), detail);
    }

    private BusinessException unavailable(ResourceAccessException e) {
        log.warn("AI 服务不可达: {}", e.getMessage());
        return new BusinessException(503, "AI 服务暂时不可用，请稍后再试");
    }

    /** 从引擎的 {"detail": ...} 取消息；Pydantic 的 422 detail 是数组，取不到就用兜底文案 */
    private String extractDetail(RestClientResponseException e) {
        try {
            String body = e.getResponseBodyAsString();
            if (body == null || body.isBlank()) {
                return e.getMessage();
            }
            JsonNode detail = objectMapper.readTree(body).path("detail");
            return detail.isTextual() ? detail.asText() : "请求参数不合法";
        } catch (Exception ex) {
            return e.getMessage();
        }
    }
}
