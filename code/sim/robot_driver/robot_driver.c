/**
 * @file robot_driver.c
 * @brief AUBO-i5 机械臂控制器 - 占位桩实现
 * 
 * 本程序作为 AUBO-i5 机械臂的 C 语言驱动层占位桩，
 * 通过 UDP 协议接收来自 Python 主控程序的指令（PICK/PLACE），
 * 模拟机械臂运动并返回执行结果。
 * 
 * 真实机器接口、IP地址、端口号等参数暂未确定，
 * 采用命令行参数方式传入，便于后续配置。
 * 
 * 通信协议：
 *   - 指令格式（JSON）：{"cmd": "PICK", "color": "<color>", "x": <x>, "y": <y>, "deg": <deg>}
 *   - 响应格式（JSON）：{"success": <true/false>, "message": "<msg>"}
 * 
 * @author 王培如 (B)
 * @date 2026-07-13
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/* ==================== 配置参数 ==================== */

/**
 * @def DEFAULT_PORT
 * @brief 默认监听端口号
 * 
 * 真实环境中，此端口需与 Python 端配置一致。
 * 可通过命令行参数 -p 指定其他端口。
 */
#define DEFAULT_PORT 5000

/**
 * @def BUFFER_SIZE
 * @brief UDP 接收缓冲区大小（字节）
 */
#define BUFFER_SIZE 1024

/**
 * @def MAX_JSON_LEN
 * @brief JSON 响应最大长度（字节）
 */
#define MAX_JSON_LEN 512

/**
 * @def MAX_COLOR_LEN
 * @brief 颜色字符串最大长度
 */
#define MAX_COLOR_LEN 32

/* ==================== 数据结构 ==================== */

/**
 * @struct Pose
 * @brief 位姿数据结构（机器人基座坐标系）
 * 
 * 包含 X、Y 坐标（毫米）和旋转角度（度）。
 */
typedef struct {
    float x;   /**< X 坐标（mm） */
    float y;   /**< Y 坐标（mm） */
    float deg; /**< 旋转角度（度） */
} Pose;

/* ==================== 函数声明 ==================== */

/**
 * @brief 发送响应给客户端
 * 
 * 将执行结果封装为 JSON 格式并发送回 Python 主控程序。
 * 
 * @param sockfd UDP socket 文件描述符
 * @param client_addr 客户端地址结构
 * @param client_len 客户端地址长度
 * @param success 执行是否成功（1=成功，0=失败）
 * @param message 执行结果描述信息
 */
void send_response(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                   int success, const char *message);

/**
 * @brief 解析 PICK 指令
 * 
 * 从 JSON 字符串中提取抓取指令的参数：颜色和目标位姿。
 * 
 * @param json 原始 JSON 指令字符串
 * @param color 输出参数：方块颜色
 * @param pose 输出参数：目标位姿
 * @return 解析是否成功（1=成功）
 */
int parse_pick(const char *json, char *color, Pose *pose);

/**
 * @brief 解析 PLACE 指令
 * 
 * 从 JSON 字符串中提取放置指令的参数：方块颜色、托盘颜色和目标位姿。
 * 
 * @param json 原始 JSON 指令字符串
 * @param block_color 输出参数：方块颜色
 * @param tray_color 输出参数：托盘颜色
 * @param pose 输出参数：目标位姿
 * @return 解析是否成功（1=成功）
 */
int parse_place(const char *json, char *block_color, char *tray_color, Pose *pose);

/**
 * @brief 处理抓取指令（占位桩）
 * 
 * 模拟机械臂抓取动作，打印执行日志。
 * 真实环境中需调用 AUBO SDK 实现实际运动控制。
 * 
 * @param sockfd UDP socket 文件描述符
 * @param client_addr 客户端地址结构
 * @param client_len 客户端地址长度
 * @param json 原始 JSON 指令字符串
 */
void handle_pick(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                 const char *json);

/**
 * @brief 处理放置指令（占位桩）
 * 
 * 模拟机械臂放置动作，打印执行日志。
 * 真实环境中需调用 AUBO SDK 实现实际运动控制。
 * 
 * @param sockfd UDP socket 文件描述符
 * @param client_addr 客户端地址结构
 * @param client_len 客户端地址长度
 * @param json 原始 JSON 指令字符串
 */
void handle_place(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                  const char *json);

/**
 * @brief 打印使用说明
 * 
 * 显示命令行参数用法。
 */
void print_usage(const char *prog_name);

/* ==================== 函数实现 ==================== */

void send_response(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                   int success, const char *message) {
    char response[MAX_JSON_LEN];
    /* 构造 JSON 响应 */
    snprintf(response, MAX_JSON_LEN, 
             "{\"success\":%d,\"message\":\"%s\"}", 
             success, message);
    /* 发送响应 */
    sendto(sockfd, response, strlen(response), 0, 
           (struct sockaddr*)client_addr, client_len);
}

int parse_pick(const char *json, char *color, Pose *pose) {
    char *token;
    char copy[BUFFER_SIZE];
    
    /* 初始化输出参数 */
    memset(color, 0, MAX_COLOR_LEN);
    memset(pose, 0, sizeof(Pose));
    
    /* 复制一份用于解析，避免修改原字符串 */
    strncpy(copy, json, BUFFER_SIZE - 1);
    copy[BUFFER_SIZE - 1] = '\0';
    
    /* 解析颜色字段 */
    token = strstr(copy, "\"color\":\"");
    if (token) {
        sscanf(token, "\"color\":\"%[^\"]\"", color);
    }
    
    /* 解析 X 坐标 */
    token = strstr(copy, "\"x\":");
    if (token) {
        sscanf(token, "\"x\":%f", &pose->x);
    }
    
    /* 解析 Y 坐标 */
    token = strstr(copy, "\"y\":");
    if (token) {
        sscanf(token, "\"y\":%f", &pose->y);
    }
    
    /* 解析角度 */
    token = strstr(copy, "\"deg\":");
    if (token) {
        sscanf(token, "\"deg\":%f", &pose->deg);
    }
    
    return 1;
}

int parse_place(const char *json, char *block_color, char *tray_color, Pose *pose) {
    char *token;
    char copy[BUFFER_SIZE];
    
    /* 初始化输出参数 */
    memset(block_color, 0, MAX_COLOR_LEN);
    memset(tray_color, 0, MAX_COLOR_LEN);
    memset(pose, 0, sizeof(Pose));
    
    /* 复制一份用于解析，避免修改原字符串 */
    strncpy(copy, json, BUFFER_SIZE - 1);
    copy[BUFFER_SIZE - 1] = '\0';
    
    /* 解析方块颜色 */
    token = strstr(copy, "\"block_color\":\"");
    if (token) {
        sscanf(token, "\"block_color\":\"%[^\"]\"", block_color);
    }
    
    /* 解析托盘颜色 */
    token = strstr(copy, "\"tray_color\":\"");
    if (token) {
        sscanf(token, "\"tray_color\":\"%[^\"]\"", tray_color);
    }
    
    /* 解析 X 坐标 */
    token = strstr(copy, "\"x\":");
    if (token) {
        sscanf(token, "\"x\":%f", &pose->x);
    }
    
    /* 解析 Y 坐标 */
    token = strstr(copy, "\"y\":");
    if (token) {
        sscanf(token, "\"y\":%f", &pose->y);
    }
    
    /* 解析角度 */
    token = strstr(copy, "\"deg\":");
    if (token) {
        sscanf(token, "\"deg\":%f", &pose->deg);
    }
    
    return 1;
}

void handle_pick(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                 const char *json) {
    char color[MAX_COLOR_LEN];
    Pose pose = {0};
    
    /* 解析指令参数 */
    parse_pick(json, color, &pose);
    
    /* 打印执行日志 */
    printf("[C-DRIVER] ==================== PICK 指令 ====================\n");
    printf("[C-DRIVER] 方块颜色: %s\n", color);
    printf("[C-DRIVER] 目标坐标: (%.2f, %.2f) mm\n", pose.x, pose.y);
    printf("[C-DRIVER] 目标角度: %.2f°\n", pose.deg);
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    /* ==================== 占位桩：模拟抓取动作 ==================== */
    /* 真实环境中，此处需调用 AUBO SDK 实现以下步骤：
     * 1. MoveJ 运动到目标上方安全高度
     * 2. MoveL 直线下降到抓取高度
     * 3. 控制吸盘吸合（设置 IO 端口）
     * 4. MoveL 直线上抬回到安全高度
     * 
     * AUBO SDK 典型调用示例（待确认）：
     *   aubo_robot.move_joint(target_joints, speed, acceleration);
     *   aubo_robot.move_line(target_position, speed, acceleration);
     *   aubo_robot.set_io(suction_cup_io, IO_HIGH);
     */
    printf("[C-DRIVER] [SIM] 阶段1: MoveJ 移至目标上方安全高度...\n");
    printf("[C-DRIVER] [SIM] 阶段2: MoveL 下降到抓取高度...\n");
    printf("[C-DRIVER] [SIM] 阶段3: 激活吸盘吸合...\n");
    printf("[C-DRIVER] [SIM] 阶段4: MoveL 上抬回到安全高度...\n");
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    /* 发送成功响应 */
    send_response(sockfd, client_addr, client_len, 1, "Pick successful");
}

void handle_place(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                  const char *json) {
    char block_color[MAX_COLOR_LEN];
    char tray_color[MAX_COLOR_LEN];
    Pose pose = {0};
    
    /* 解析指令参数 */
    parse_place(json, block_color, tray_color, &pose);
    
    /* 打印执行日志 */
    printf("[C-DRIVER] ==================== PLACE 指令 ====================\n");
    printf("[C-DRIVER] 方块颜色: %s\n", block_color);
    printf("[C-DRIVER] 托盘颜色: %s\n", tray_color);
    printf("[C-DRIVER] 目标坐标: (%.2f, %.2f) mm\n", pose.x, pose.y);
    printf("[C-DRIVER] 目标角度: %.2f°\n", pose.deg);
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    /* ==================== 占位桩：模拟放置动作 ==================== */
    /* 真实环境中，此处需调用 AUBO SDK 实现以下步骤：
     * 1. MoveJ 运动到目标槽上方安全高度
     * 2. MoveL 直线下降到放置高度
     * 3. 控制吸盘释放（设置 IO 端口）
     * 4. MoveL 直线上抬回到安全高度
     * 
     * AUBO SDK 典型调用示例（待确认）：
     *   aubo_robot.move_joint(target_joints, speed, acceleration);
     *   aubo_robot.move_line(target_position, speed, acceleration);
     *   aubo_robot.set_io(suction_cup_io, IO_LOW);
     */
    printf("[C-DRIVER] [SIM] 阶段1: MoveJ 移至目标槽上方安全高度...\n");
    printf("[C-DRIVER] [SIM] 阶段2: MoveL 下降到放置高度...\n");
    printf("[C-DRIVER] [SIM] 阶段3: 释放吸盘...\n");
    printf("[C-DRIVER] [SIM] 阶段4: MoveL 上抬回到安全高度...\n");
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    /* 发送成功响应 */
    send_response(sockfd, client_addr, client_len, 1, "Place successful");
}

void print_usage(const char *prog_name) {
    printf("用法: %s [-p 端口号]\n", prog_name);
    printf("\n");
    printf("AUBO-i5 机械臂控制器 - 占位桩实现\n");
    printf("\n");
    printf("选项:\n");
    printf("  -p, --port <port>   指定监听端口号 (默认: %d)\n", DEFAULT_PORT);
    printf("  -h, --help          显示此帮助信息\n");
    printf("\n");
    printf("说明:\n");
    printf("  本程序通过 UDP 协议接收来自 Python 主控程序的指令，\n");
    printf("  模拟机械臂运动并返回执行结果。\n");
    printf("\n");
    printf("  真实机器接口、IP地址等参数暂未确定，\n");
    printf("  采用命令行参数方式传入，便于后续配置。\n");
}

/* ==================== 主函数 ==================== */

/**
 * @brief 主函数
 * 
 * 初始化 UDP socket，监听指定端口，接收并处理指令。
 * 
 * @param argc 命令行参数数量
 * @param argv 命令行参数数组
 * @return 程序退出码
 */
int main(int argc, char *argv[]) {
    int sockfd;
    struct sockaddr_in server_addr, client_addr;
    char buffer[BUFFER_SIZE];
    int client_len;
    int port = DEFAULT_PORT;
    
    /* ==================== 解析命令行参数 ==================== */
    for (int i = 1; i < argc; i++) {
        if ((strcmp(argv[i], "-p") == 0 || strcmp(argv[i], "--port") == 0) && i + 1 < argc) {
            port = atoi(argv[++i]);
            if (port <= 0 || port > 65535) {
                fprintf(stderr, "错误: 端口号必须在 1-65535 之间\n");
                return EXIT_FAILURE;
            }
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return EXIT_SUCCESS;
        } else {
            fprintf(stderr, "错误: 未知选项 '%s'\n", argv[i]);
            print_usage(argv[0]);
            return EXIT_FAILURE;
        }
    }
    
    /* ==================== 创建 UDP Socket ==================== */
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        perror("[C-DRIVER] 错误: 创建 socket 失败");
        exit(EXIT_FAILURE);
    }
    
    /* ==================== 设置服务器地址 ==================== */
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;         /* IPv4 */
    server_addr.sin_addr.s_addr = INADDR_ANY; /* 监听所有网卡 */
    server_addr.sin_port = htons(port);       /* 监听端口 */
    
    /* ==================== 绑定端口 ==================== */
    if (bind(sockfd, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        perror("[C-DRIVER] 错误: 绑定端口失败");
        close(sockfd);
        exit(EXIT_FAILURE);
    }
    
    /* ==================== 打印启动信息 ==================== */
    printf("[C-DRIVER] ==============================================\n");
    printf("[C-DRIVER] AUBO-i5 机械臂控制器 (占位桩)\n");
    printf("[C-DRIVER] ==============================================\n");
    printf("[C-DRIVER] 监听端口: %d\n", port);
    printf("[C-DRIVER] 等待 Python 主控程序连接...\n");
    printf("[C-DRIVER] ==============================================\n");
    printf("\n");
    
    /* ==================== 主循环：接收并处理指令 ==================== */
    while (1) {
        client_len = sizeof(client_addr);
        
        /* 接收 UDP 数据 */
        int n = recvfrom(sockfd, buffer, BUFFER_SIZE - 1, 0, 
                         (struct sockaddr*)&client_addr, &client_len);
        if (n < 0) {
            perror("[C-DRIVER] 错误: 接收数据失败");
            continue;
        }
        
        /* 添加字符串结束符 */
        buffer[n] = '\0';
        
        /* 打印接收到的原始数据 */
        printf("[C-DRIVER] 接收到数据 (%d 字节):\n", n);
        printf("[C-DRIVER] %s\n", buffer);
        
        /* 根据指令类型分发处理 */
        if (strstr(buffer, "\"cmd\":\"PICK\"") || strstr(buffer, "\"cmd\":\"pick\"")) {
            handle_pick(sockfd, &client_addr, client_len, buffer);
        } else if (strstr(buffer, "\"cmd\":\"PLACE\"") || strstr(buffer, "\"cmd\":\"place\"")) {
            handle_place(sockfd, &client_addr, client_len, buffer);
        } else {
            printf("[C-DRIVER] 错误: 未知指令\n");
            send_response(sockfd, &client_addr, client_len, 0, "Unknown command");
        }
        
        /* 输出分隔线 */
        printf("\n");
    }
    
    /* ==================== 清理资源（实际不会执行到这里） ==================== */
    close(sockfd);
    return 0;
}
