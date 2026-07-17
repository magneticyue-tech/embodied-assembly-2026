/** robot_driver.c 协议解析与幂等缓存单元测试。 */
/* <!--A--> */
#define main robot_driver_program_main
#include "robot_driver.c"
#undef main

#include <assert.h>

int main(void) {
    char request_id[MAX_REQUEST_ID_LEN + 1];
    char color[MAX_COLOR_LEN];
    char tray_color[MAX_COLOR_LEN];
    Pose pose;

    const char *pick =
        "{\"cmd\":\"PICK\",\"color\":\"red\",\"x\":1.5,\"y\":2,"
        "\"deg\":-3,\"request_id\":\"abc12345\"}";
    assert(parse_request_id(pick, request_id));
    assert(strcmp(request_id, "abc12345") == 0);
    assert(parse_pick(pick, color, &pose));
    assert(strcmp(color, "red") == 0);
    assert(fabsf(pose.x - 1.5f) < 0.001f);

    const char *place =
        "{\"cmd\": \"PLACE\", \"block_color\": \"red\", "
        "\"tray_color\": \"blue\", \"x\": 1, \"y\": 2, "
        "\"deg\": 3, \"request_id\": \"place001\"}";
    assert(parse_place(place, color, tray_color, &pose));
    assert(strcmp(tray_color, "blue") == 0);

    assert(!parse_pick(
        "{\"cmd\":\"PICK\",\"color\":\"red\",\"x\":1,\"y\":2}",
        color,
        &pose
    ));
    assert(!parse_pick(
        "{\"cmd\":\"PICK\",\"color\":\"black\",\"x\":1,\"y\":2,"
        "\"deg\":3}",
        color,
        &pose
    ));
    assert(!parse_request_id(
        "{\"request_id\":\"abcdefghijklmnopqrstuvwxyz1234567890\"}",
        request_id
    ));

    uint64_t payload_hash = hash_payload(pick);
    remember_response("abc12345", payload_hash, 1, "Pick successful");
    int cached_index = find_processed_request("abc12345");
    assert(cached_index >= 0);
    assert(processed_cache[cached_index].payload_hash == payload_hash);
    assert(processed_cache[cached_index].success == 1);

    puts("robot_driver tests passed");
    return 0;
}
