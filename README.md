tornado_auto_cache
==================

基于tornado的自动设置memcache 的修饰器，可以根据配置信息取url中的某些字段做为cache 的key

测试：
curl http://localhost:port/cps/getSearch
这个请求将会走到getSearch函数处，如果设置了缓存自动将请求结果保存到缓存中
