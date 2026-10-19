package com.agentadmin.config;

import com.agentadmin.common.RequireAdmin;
import com.agentadmin.util.JwtUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.method.HandlerMethod;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * JwtInterceptor 单元测试：token 校验 + @RequireAdmin 的角色门槛
 * 纯单元测试：直接 new，不启动 Spring 容器
 */
class JwtInterceptorTest {

    /** HS256 要求密钥 ≥ 256 bit（32 字节） */
    private static final String SECRET = "unit-test-secret-key-0123456789-abcdefghij";

    private final JwtUtil jwtUtil = new JwtUtil(SECRET, 1);
    private final JwtInterceptor interceptor = new JwtInterceptor(jwtUtil, new ObjectMapper());

    /** 假的接口：一个标了管理员，一个没标 */
    static class DummyController {
        @RequireAdmin
        public void adminOnly() {
        }

        public void open() {
        }
    }

    private HandlerMethod handler(String method) throws NoSuchMethodException {
        return new HandlerMethod(new DummyController(), DummyController.class.getMethod(method));
    }

    private MockHttpServletRequest withToken(Long userId, String roleCode) {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("Authorization", "Bearer " + jwtUtil.generate(userId, roleCode));
        return request;
    }

    @Test
    @DisplayName("未登录：401")
    void missingToken() throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();

        boolean pass = interceptor.preHandle(new MockHttpServletRequest(), response, handler("open"));

        assertThat(pass).isFalse();
        assertThat(response.getStatus()).isEqualTo(401);
    }

    @Test
    @DisplayName("普通用户访问管理接口：403")
    void userCannotAccessAdminEndpoint() throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();

        boolean pass = interceptor.preHandle(withToken(1L, "USER"), response, handler("adminOnly"));

        assertThat(pass).isFalse();
        assertThat(response.getStatus()).isEqualTo(403);
    }

    @Test
    @DisplayName("管理员访问管理接口：放行，并把角色码放进 request")
    void adminPassesAdminEndpoint() throws Exception {
        MockHttpServletRequest request = withToken(1L, "ADMIN");
        MockHttpServletResponse response = new MockHttpServletResponse();

        boolean pass = interceptor.preHandle(request, response, handler("adminOnly"));

        assertThat(pass).isTrue();
        assertThat(request.getAttribute(JwtInterceptor.ATTR_USER_ID)).isEqualTo(1L);
        assertThat(request.getAttribute(JwtInterceptor.ATTR_ROLE_CODE)).isEqualTo("ADMIN");
    }

    @Test
    @DisplayName("没标 @RequireAdmin 的接口：普通用户照常放行")
    void userPassesOpenEndpoint() throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();

        boolean pass = interceptor.preHandle(withToken(1L, "USER"), response, handler("open"));

        assertThat(pass).isTrue();
    }
}
