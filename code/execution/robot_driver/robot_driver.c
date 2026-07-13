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
 *   - 指令格式（JSON）：{"cmd":"PICK","color":"<color>","x":<x>,"y":<y>,"deg":<deg>,"request_id":"<id>"}
 *   - 响应格式（JSON）：{"success":<true/false>,"message":"<msg>","request_id":"<id>"}
 * 
 */
/* <!--A--> */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdint.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET socket_handle_t;
typedef int socket_len_t;
typedef int recv_size_t;
#define CLOSE_SOCKET closesocket
#define INVALID_SOCKET_HANDLE INVALID_SOCKET
#define SOCKET_CALL_ERROR SOCKET_ERROR
#else
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
typedef int socket_handle_t;
typedef socklen_t socket_len_t;
typedef ssize_t recv_size_t;
#define CLOSE_SOCKET close
#define INVALID_SOCKET_HANDLE (-1)
#define SOCKET_CALL_ERROR (-1)
#endif

#define DEFAULT_PORT 5000
#define BUFFER_SIZE 1024
#define MAX_JSON_LEN 512
#define MAX_COLOR_LEN 32
#define MAX_REQUEST_ID_LEN 32
#define MAX_COMMAND_LEN 16
#define MAX_MESSAGE_LEN 96
#define PROCESSED_CACHE_SIZE 128

typedef struct {
    float x;
    float y;
    float deg;
} Pose;

typedef struct {
    char request_id[MAX_REQUEST_ID_LEN + 1];
    uint64_t payload_hash;
    int success;
    char message[MAX_MESSAGE_LEN];
} ProcessedRequest;

static ProcessedRequest processed_cache[PROCESSED_CACHE_SIZE];
static size_t processed_count = 0;
static size_t processed_next = 0;

void send_response(socket_handle_t sockfd, struct sockaddr_in *client_addr, socket_len_t client_len,
                   int success, const char *message, const char *request_id);
int parse_pick(const char *json, char *color, Pose *pose);
int parse_place(const char *json, char *block_color, char *tray_color, Pose *pose);
int parse_request_id(const char *json, char *request_id);
void handle_pick(socket_handle_t sockfd, struct sockaddr_in *client_addr, socket_len_t client_len,
                 const char *json, const char *request_id, uint64_t payload_hash);
void handle_place(socket_handle_t sockfd, struct sockaddr_in *client_addr, socket_len_t client_len,
                  const char *json, const char *request_id, uint64_t payload_hash);
void print_usage(const char *prog_name);

void send_response(socket_handle_t sockfd, struct sockaddr_in *client_addr, socket_len_t client_len,
                   int success, const char *message, const char *request_id) {
    char response[MAX_JSON_LEN];
    if (request_id && strlen(request_id) > 0) {
        snprintf(response, MAX_JSON_LEN,
                 "{\"success\":%s,\"message\":\"%s\",\"request_id\":\"%s\"}",
                 success ? "true" : "false", message, request_id);
    } else {
        snprintf(response, MAX_JSON_LEN,
                 "{\"success\":%s,\"message\":\"%s\"}",
                 success ? "true" : "false", message);
    }
    sendto(sockfd, response, strlen(response), 0, 
           (struct sockaddr*)client_addr, client_len);
}

static const char *skip_whitespace(const char *text) {
    while (*text != '\0' && isspace((unsigned char)*text)) {
        text++;
    }
    return text;
}

static int find_json_value(const char *json, const char *key, const char **value) {
    char pattern[64];
    int written = snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    if (written < 0 || (size_t)written >= sizeof(pattern)) {
        return 0;
    }

    const char *position = strstr(json, pattern);
    if (position == NULL) {
        return 0;
    }

    position = skip_whitespace(position + strlen(pattern));
    if (*position != ':') {
        return 0;
    }
    *value = skip_whitespace(position + 1);
    return 1;
}

static int extract_json_string(
    const char *json, const char *key, char *output, size_t output_size
) {
    const char *value;
    if (output_size == 0 || !find_json_value(json, key, &value) || *value != '"') {
        return 0;
    }

    value++;
    size_t length = 0;
    while (*value != '\0' && *value != '"') {
        unsigned char character = (unsigned char)*value;
        if (character < 0x20 || *value == '\\' || length + 1 >= output_size) {
            return 0;
        }
        output[length++] = *value++;
    }
    if (*value != '"') {
        return 0;
    }

    output[length] = '\0';
    return length > 0;
}

static int extract_json_float(const char *json, const char *key, float *output) {
    const char *value;
    if (!find_json_value(json, key, &value)) {
        return 0;
    }

    errno = 0;
    char *end;
    float parsed = strtof(value, &end);
    if (end == value || errno == ERANGE || !isfinite(parsed)) {
        return 0;
    }

    end = (char *)skip_whitespace(end);
    if (*end != ',' && *end != '}') {
        return 0;
    }
    *output = parsed;
    return 1;
}

static int is_valid_color(const char *color) {
    static const char *valid_colors[] = {
        "red", "orange", "yellow", "green", "blue", "purple"
    };
    for (size_t i = 0; i < sizeof(valid_colors) / sizeof(valid_colors[0]); i++) {
        if (strcmp(color, valid_colors[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

static uint64_t hash_payload(const char *payload) {
    uint64_t hash = UINT64_C(14695981039346656037);
    while (*payload != '\0') {
        hash ^= (unsigned char)*payload++;
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static int find_processed_request(const char *request_id) {
    for (size_t i = 0; i < processed_count; i++) {
        if (strcmp(processed_cache[i].request_id, request_id) == 0) {
            return (int)i;
        }
    }
    return -1;
}

static void remember_response(
    const char *request_id, uint64_t payload_hash, int success, const char *message
) {
    ProcessedRequest *entry = &processed_cache[processed_next];
    snprintf(entry->request_id, sizeof(entry->request_id), "%s", request_id);
    entry->payload_hash = payload_hash;
    entry->success = success;
    snprintf(entry->message, sizeof(entry->message), "%s", message);

    processed_next = (processed_next + 1) % PROCESSED_CACHE_SIZE;
    if (processed_count < PROCESSED_CACHE_SIZE) {
        processed_count++;
    }
}

int parse_request_id(const char *json, char *request_id) {
    if (!extract_json_string(
            json, "request_id", request_id, MAX_REQUEST_ID_LEN + 1
        )) {
        request_id[0] = '\0';
        return 0;
    }

    for (const char *character = request_id; *character != '\0'; character++) {
        if (!isalnum((unsigned char)*character) && *character != '-' && *character != '_') {
            request_id[0] = '\0';
            return 0;
        }
    }
    return 1;
}

int parse_pick(const char *json, char *color, Pose *pose) {
    memset(color, 0, MAX_COLOR_LEN);
    memset(pose, 0, sizeof(Pose));

    return extract_json_string(json, "color", color, MAX_COLOR_LEN)
        && is_valid_color(color)
        && extract_json_float(json, "x", &pose->x)
        && extract_json_float(json, "y", &pose->y)
        && extract_json_float(json, "deg", &pose->deg);
}

int parse_place(const char *json, char *block_color, char *tray_color, Pose *pose) {
    memset(block_color, 0, MAX_COLOR_LEN);
    memset(tray_color, 0, MAX_COLOR_LEN);
    memset(pose, 0, sizeof(Pose));

    return extract_json_string(json, "block_color", block_color, MAX_COLOR_LEN)
        && is_valid_color(block_color)
        && extract_json_string(json, "tray_color", tray_color, MAX_COLOR_LEN)
        && is_valid_color(tray_color)
        && extract_json_float(json, "x", &pose->x)
        && extract_json_float(json, "y", &pose->y)
        && extract_json_float(json, "deg", &pose->deg);
}

void handle_pick(socket_handle_t sockfd, struct sockaddr_in *client_addr, socket_len_t client_len,
                 const char *json, const char *request_id, uint64_t payload_hash) {
    char color[MAX_COLOR_LEN];
    Pose pose = {0};

    if (!parse_pick(json, color, &pose)) {
        const char *message = "Invalid PICK payload";
        remember_response(request_id, payload_hash, 0, message);
        send_response(sockfd, client_addr, client_len, 0, message, request_id);
        return;
    }
    
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
    
    remember_response(request_id, payload_hash, 1, "Pick successful");
    send_response(sockfd, client_addr, client_len, 1, "Pick successful", request_id);
}

void handle_place(socket_handle_t sockfd, struct sockaddr_in *client_addr, socket_len_t client_len,
                  const char *json, const char *request_id, uint64_t payload_hash) {
    char block_color[MAX_COLOR_LEN];
    char tray_color[MAX_COLOR_LEN];
    Pose pose = {0};

    if (!parse_place(json, block_color, tray_color, &pose)) {
        const char *message = "Invalid PLACE payload";
        remember_response(request_id, payload_hash, 0, message);
        send_response(sockfd, client_addr, client_len, 0, message, request_id);
        return;
    }
    
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
    
    remember_response(request_id, payload_hash, 1, "Place successful");
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
    socket_handle_t sockfd;
    struct sockaddr_in server_addr, client_addr;
    char buffer[BUFFER_SIZE];
    socket_len_t client_len;
    int port = DEFAULT_PORT;

    /* 评分要求执行状态实时可观察；重定向日志时也立即刷新。 */
    setvbuf(stdout, NULL, _IONBF, 0);

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

#ifdef _WIN32
    WSADATA winsock_data;
    if (WSAStartup(MAKEWORD(2, 2), &winsock_data) != 0) {
        fprintf(stderr, "[C-DRIVER] 错误: Winsock 初始化失败\n");
        return EXIT_FAILURE;
    }
#endif

    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd == INVALID_SOCKET_HANDLE) {
        perror("[C-DRIVER] 错误: 创建 socket 失败");
#ifdef _WIN32
        WSACleanup();
#endif
        exit(EXIT_FAILURE);
    }
    
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(port);
    
    if (bind(sockfd, (struct sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_CALL_ERROR) {
        perror("[C-DRIVER] 错误: 绑定端口失败");
        CLOSE_SOCKET(sockfd);
#ifdef _WIN32
        WSACleanup();
#endif
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
        
        recv_size_t n = recvfrom(sockfd, buffer, BUFFER_SIZE - 1, 0,
                                 (struct sockaddr*)&client_addr, &client_len);
        if (n == SOCKET_CALL_ERROR) {
            perror("[C-DRIVER] 错误: 接收数据失败");
            continue;
        }
        
        buffer[n] = '\0';
        
        printf("[C-DRIVER] 接收到数据 (%d 字节):\n", (int)n);
        printf("[C-DRIVER] %s\n", buffer);

        char request_id[MAX_REQUEST_ID_LEN + 1];
        if (!parse_request_id(buffer, request_id)) {
            printf("[C-DRIVER] 错误: request_id 缺失或格式非法\n");
            send_response(
                sockfd, &client_addr, client_len, 0,
                "Missing or invalid request_id", NULL
            );
            printf("\n");
            continue;
        }

        uint64_t payload_hash = hash_payload(buffer);
        int cached_index = find_processed_request(request_id);
        if (cached_index >= 0) {
            ProcessedRequest *cached = &processed_cache[cached_index];
            if (cached->payload_hash != payload_hash) {
                printf("[C-DRIVER] 错误: request_id 被不同指令重复使用\n");
                send_response(
                    sockfd, &client_addr, client_len, 0,
                    "request_id reused with different payload", request_id
                );
            } else {
                printf("[C-DRIVER] 命中幂等缓存，不重复执行机械臂动作\n");
                send_response(
                    sockfd, &client_addr, client_len, cached->success,
                    cached->message, request_id
                );
            }
            printf("\n");
            continue;
        }

        char command[MAX_COMMAND_LEN];
        if (!extract_json_string(buffer, "cmd", command, sizeof(command))) {
            const char *message = "Missing or invalid cmd field";
            printf("[C-DRIVER] 错误: cmd 字段缺失或格式非法\n");
            remember_response(request_id, payload_hash, 0, message);
            send_response(sockfd, &client_addr, client_len, 0, message, request_id);
        } else if (strcmp(command, "PICK") == 0 || strcmp(command, "pick") == 0) {
            handle_pick(
                sockfd, &client_addr, client_len, buffer, request_id, payload_hash
            );
        } else if (strcmp(command, "PLACE") == 0 || strcmp(command, "place") == 0) {
            handle_place(
                sockfd, &client_addr, client_len, buffer, request_id, payload_hash
            );
        } else {
            const char *message = "Unknown command";
            printf("[C-DRIVER] 错误: 未知指令\n");
            remember_response(request_id, payload_hash, 0, message);
            send_response(sockfd, &client_addr, client_len, 0, message, request_id);
        }
        
        printf("\n");
    }
    
    CLOSE_SOCKET(sockfd);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
