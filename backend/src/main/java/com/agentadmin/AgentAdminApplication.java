package com.agentadmin;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.agentadmin.mapper")
public class AgentAdminApplication {

    public static void main(String[] args) {
        SpringApplication.run(AgentAdminApplication.class, args);
    }
}
