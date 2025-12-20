from app.redis_manager import redis_manager


def test_cache_and_get_json_item_method():
    redis_manager.cache_json_item("test-item", {"item": 41})
    test_item = redis_manager.get_json_item("test-item")
    assert test_item == {"item": 41}
    

def test_delete_key_method():
    redis_manager.cache_json_item("test-item", {"item": 41})
    redis_manager.delete_key("test_item")
    test_item = redis_manager.get_json_item("test_item")
    assert test_item is None