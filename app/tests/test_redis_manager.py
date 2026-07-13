from app.redis_manager import redis_manager


async def test_cache_and_get_json_item_method():
    await redis_manager.cache_json_item("test-item", {"item": 41})
    test_item = await redis_manager.get_json_item("test-item")
    assert test_item == {"item": 41}


async def test_delete_key_method():
    await redis_manager.cache_json_item("test-item", {"item": 41})
    await redis_manager.delete_key("test_item")
    test_item = await redis_manager.get_json_item("test_item")
    assert test_item is None
