package com.agentadmin.common;

/**
 * 当前登录者：由拦截器从 JWT 解出、Controller 组装后往下传
 *
 * 单独成一个类型而不是每次传两个参数：身份和角色总是一起用，
 * 两个裸参数容易传错位
 */
public record Caller(Long userId, String roleCode) {

    /** 管理员角色码，与 role 表里的 code 对应 */
    public static final String ROLE_ADMIN = "ADMIN";

    public Caller {
        // 统一成空串：改造前签发的 token 里没有 roleCode，让 null 散到各处判断更麻烦
        roleCode = roleCode == null ? "" : roleCode;
    }

    /** 角色语义只在这一层解释 */
    public boolean isAdmin() {
        return ROLE_ADMIN.equals(roleCode);
    }
}
