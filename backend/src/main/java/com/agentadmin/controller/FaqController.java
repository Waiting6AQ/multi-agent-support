package com.agentadmin.controller;

import com.agentadmin.common.RequireAdmin;
import com.agentadmin.common.Result;
import com.agentadmin.dto.FaqInfo;
import com.agentadmin.dto.FaqListResponse;
import com.agentadmin.dto.FaqRequest;
import com.agentadmin.service.FaqService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** FAQ 管理：维护技术支持 Agent 的知识库，四个接口都只对管理员开放 */
@RestController
@RequestMapping("/api/faqs")
@RequiredArgsConstructor
public class FaqController {

    private final FaqService faqService;

    @RequireAdmin
    @GetMapping
    public Result<FaqListResponse> list() {
        return Result.ok(faqService.list());
    }

    @RequireAdmin
    @PostMapping
    public Result<FaqInfo> create(@Valid @RequestBody FaqRequest req) {
        return Result.ok(faqService.create(req));
    }

    @RequireAdmin
    @PutMapping("/{id}")
    public Result<FaqInfo> update(@PathVariable int id, @Valid @RequestBody FaqRequest req) {
        return Result.ok(faqService.update(id, req));
    }

    @RequireAdmin
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable int id) {
        faqService.delete(id);
        return Result.ok();
    }
}
