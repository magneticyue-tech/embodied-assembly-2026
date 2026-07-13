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
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define DEFAULT_PORT 5000
#define BUFFER_SIZE 1024
#define MAX_JSON_LEN 512
#define MAX_COLOR_LEN 32

typedef struct {
    float x;
    float y;
    float deg;
} Pose;

void send_response(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                   int success, const char *message, const char *request_id);
int parse_pick(const char *json, char *color, Pose *pose);
int parse_place(const char *json, char *block_color, char *tray_color, Pose *pose);
void parse_request_id(const char *json, char *request_id);
void handle_pick(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                 const char *json);
void handle_place(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                  const char *json);
void print_usage(const char *prog_name);

void send_response(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                   int success, const char *message, const char *request_id) {
    char response[MAX_JSON_LEN];
    if (request_id && strlen(request_id) > 0) {
        snprintf(response, MAX_JSON_LEN, 
                 "{\"success\":%d,\"message\":\"%s\",\"request_id\":\"%s\"}", 
                 success, message, request_id);
    } else {
        snprintf(response, MAX_JSON_LEN, 
                 "{\"success\":%d,\"message\":\"%s\"}", 
                 success, message);
    }
    sendto(sockfd, response, strlen(response), 0, 
           (struct sockaddr*)client_addr, client_len);
}

void parse_request_id(const char *json, char *request_id) {
    char *token = strstr(json, "\"request_id\":\"");
    if (token) {
        sscanf(token, "\"request_id\":\"%[^\"]\"", request_id);
    } else {
        request_id[0] = '\0';
    }
}

int parse_pick(const char *json, char *color, Pose *pose) {
    char *token;
    char copy[BUFFER_SIZE];
    
    memset(color, 0, MAX_COLOR_LEN);
    memset(pose, 0, sizeof(Pose));
    
    strncpy(copy, json, BUFFER_SIZE - 1);
    copy[BUFFER_SIZE - 1] = '\0';
    
    token = strstr(copy, "\"color\":\"");
    if (token) {
        sscanf(token, "\"color\":\"%[^\"]\"", color);
    }
    
    token = strstr(copy, "\"x\":");
    if (token) {
        sscanf(token, "\"x\":%f", &pose->x);
    }
    
    token = strstr(copy, "\"y\":");
    if (token) {
        sscanf(token, "\"y\":%f", &pose->y);
    }
    
    token = strstr(copy, "\"deg\":");
    if (token) {
        sscanf(token, "\"deg\":%f", &pose->deg);
    }
    
    return 1;
}

int parse_place(const char *json, char *block_color, char *tray_color, Pose *pose) {
    char *token;
    char copy[BUFFER_SIZE];
    
    memset(block_color, 0, MAX_COLOR_LEN);
    memset(tray_color, 0, MAX_COLOR_LEN);
    memset(pose, 0, sizeof(Pose));
    
    strncpy(copy, json, BUFFER_SIZE - 1);
    copy[BUFFER_SIZE - 1] = '\0';
    
    token = strstr(copy, "\"block_color\":\"");
    if (token) {
        sscanf(token, "\"block_color\":\"%[^\"]\"", block_color);
    }
    
    token = strstr(copy, "\"tray_color\":\"");
    if (token) {
        sscanf(token, "\"tray_color\":\"%[^\"]\"", tray_color);
    }
    
    token = strstr(copy, "\"x\":");
    if (token) {
        sscanf(token, "\"x\":%f", &pose->x);
    }
    
    token = strstr(copy, "\"y\":");
    if (token) {
        sscanf(token, "\"y\":%f", &pose->y);
    }
    
    token = strstr(copy, "\"deg\":");
    if (token) {
        sscanf(token, "\"deg\":%f", &pose->deg);
    }
    
    return 1;
}

void handle_pick(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                 const char *json) {
    char color[MAX_COLOR_LEN];
    char request_id[33];
    Pose pose = {0};
    
    parse_pick(json, color, &pose);
    parse_request_id(json, request_id);
    
    printf("[C-DRIVER] ==================== PICK 指令 ====================\n");
    printf("[C-DRIVER] 请求ID: %s\n", request_id);
    printf("[C-DRIVER] 方块颜色: %s\n", color);
    printf("[C-DRIVER] 目标坐标: (%.2f, %.2f) mm\n", pose.x, pose.y);
    printf("[C-DRIVER] 目标角度: %.2f°\n", pose.deg);
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    printf("[C-DRIVER] [SIM] 阶段1: MoveJ 移至目标上方安全高度...\n");
    printf("[C-DRIVER] [SIM] 阶段2: MoveL 下降到抓取高度...\n");
    printf("[C-DRIVER] [SIM] 阶段3: 激活吸盘吸合...\n");
    printf("[C-DRIVER] [SIM] 阶段4: MoveL 上抬回到安全高度...\n");
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    send_response(sockfd, client_addr, client_len, 1, "Pick successful", request_id);
}

void handle_place(int sockfd, struct sockaddr_in *client_addr, int client_len, 
                  const char *json) {
    char block_color[MAX_COLOR_LEN];
    char tray_color[MAX_COLOR_LEN];
    char request_id[33];
    Pose pose = {0};
    
    parse_place(json, block_color, tray_color, &pose);
    parse_request_id(json, request_id);
    
    printf("[C-DRIVER] ==================== PLACE 指令 ====================\n");
    printf("[C-DRIVER] 请求ID: %s\n", request_id);
    printf("[C-DRIVER] 方块颜色: %s\n", block_color);
    printf("[C-DRIVER] 托盘颜色: %s\n", tray_color);
    printf("[C-DRIVER] 目标坐标: (%.2f, %.2f) mm\n", pose.x, pose.y);
    printf("[C-DRIVER] 目标角度: %.2f°\n", pose.deg);
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    printf("[C-DRIVER] [SIM] 阶段1: MoveJ 移至目标槽上方安全高度...\n");
    printf("[C-DRIVER] [SIM] 阶段2: MoveL 下降到放置高度...\n");
    printf("[C-DRIVER] [SIM] 阶段3: 释放吸盘...\n");
    printf("[C-DRIVER] [SIM] 阶段4: MoveL 上抬回到安全高度...\n");
    printf("[C-DRIVER] ----------------------------------------------------\n");
    
    send_response(sockfd, client_addr, client_len, 1, "Place successful", request_id);
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
}

int main(int argc, char *argv[]) {
    int sockfd;
    struct sockaddr_in server_addr, client_addr;
    char buffer[BUFFER_SIZE];
    int client_len;
    int port = DEFAULT_PORT;
    
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
    
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        perror("[C-DRIVER] 错误: 创建 socket 失败");
        exit(EXIT_FAILURE);
    }
    
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(port);
    
    if (bind(sockfd, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        perror("[C-DRIVER] 错误: 绑定端口失败");
        close(sockfd);
        exit(EXIT_FAILURE);
    }
    
    printf("[C-DRIVER] ==============================================\n");
    printf("[C-DRIVER] AUBO-i5 机械臂控制器 (占位桩)\n");
    printf("[C-DRIVER] ==============================================\n");
    printf("[C-DRIVER] 监听端口: %d\n", port);
    printf("[C-DRIVER] 等待 Python 主控程序连接...\n");
    printf("[C-DRIVER] ==============================================\n");
    printf("\n");
    
    while (1) {
        client_len = sizeof(client_addr);
        
        int n = recvfrom(sockfd, buffer, BUFFER_SIZE - 1, 0, 
                         (struct sockaddr*)&client_addr, &client_len);
        if (n < 0) {
            perror("[C-DRIVER] 错误: 接收数据失败");
            continue;
        }
        
        buffer[n] = '\0';
        
        printf("[C-DRIVER] 接收到数据 (%d 字节):\n", n);
        printf("[C-DRIVER] %s\n", buffer);
        
        char request_id[33];
        parse_request_id(buffer, request_id);

        char *cmd_pos = strstr(buffer, "\"cmd\"");
        if (cmd_pos) {
            char *colon_pos = strchr(cmd_pos + 5, ':');
            if (colon_pos) {
                char *val_start = colon_pos + 1;
                while (*val_start == ' ') val_start++;
                if (*val_start == '"') {
                    val_start++;
                    if (strncmp(val_start, "PICK", 4) == 0 || strncmp(val_start, "pick", 4) == 0) {
                        handle_pick(sockfd, &client_addr, client_len, buffer);
                    } else if (strncmp(val_start, "PLACE", 5) == 0 || strncmp(val_start, "place", 5) == 0) {
                        handle_place(sockfd, &client_addr, client_len, buffer);
                    } else {
                        printf("[C-DRIVER] 错误: 未知指令\n");
                        send_response(sockfd, &client_addr, client_len, 0, "Unknown command", request_id);
                    }
                } else {
                    printf("[C-DRIVER] 错误: 指令格式错误\n");
                    send_response(sockfd, &client_addr, client_len, 0, "Invalid command format", request_id);
                }
            } else {
                printf("[C-DRIVER] 错误: 指令格式错误\n");
                send_response(sockfd, &client_addr, client_len, 0, "Invalid command format", request_id);
            }
        } else {
            printf("[C-DRIVER] 错误: 未找到 cmd 字段\n");
            send_response(sockfd, &client_addr, client_len, 0, "Missing cmd field", request_id);
        }
        
        printf("\n");
    }
    
    close(sockfd);
    return 0;
}
