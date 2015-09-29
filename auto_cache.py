#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Copyright (c) 2013,掌阅科技
All rights reserved.

File Name: tornado_auto_cache.py
Author: WangLichao
Created on: 2014-03-12
'''
import json
import hashlib
from functools import wraps
import tornado.ioloop
import tornado.web
import logging
import memcache
from memcache import Client

key_settings = {}

class CacheOp(object):
    '''
    操作memcache的类
    操作cache过程中加入生成专有key的逻辑
    真正key的格式{prefix}_{value}_{version}
    value如果没有特殊设置默认根据设置的请求参数值生成md5
    '''
    def __init__(self, cache, prefix):
        self.cache = cache
        self.prefix = prefix

    def make_key(self, key_gen, key_tpl=None):
        '''
        生成不带版本号的key
        param: key_gen dict 带有参数和参数的值
        param: cache_conf dict
        '''
        key = None
        if key_tpl:
            key = key_tpl % tuple(key_gen.itervalues())
            return key
        key_format = '%s_%s'
        code = hashlib.md5()
        code.update("".join(sorted(map(str, key_gen.iteritems()))))
        md5_value = code.hexdigest()
        key = key_format % (self.prefix, md5_value)
        return key

    def mem_get_ver(self):
        '''
        获取前缀对应的版本信息
        '''
        result = 0
        if not self.prefix:
            return result
        try:
            memstr = self.cache.get(self.prefix)
            if memstr == None:
                self.cache.set(self.prefix, result)
            else:
                result = memstr
        except Exception,e:
            logging.error("Error %s" % str(e), exc_info=True)
        return result

    def get(self, key, is_json=True):
        '''
        获取 mem 的数据
        @param key: 键
        @param is_json: 是否要 json
        '''
        key = "%s_%i" % (key, self.mem_get_ver())
        print 'get:%s' % key
        cache_str = None
        try:
            cache_str = self.cache.get(key)
        except Exception,e:
            print e
            logging.error("Error %s" % str(e),exc_info=True)
        result = cache_str
        if is_json:
            result = json.loads(cache_str) if isinstance(cache_str, str) else cache_str
        return result

    def set(self, key, value, timeout=60*60):
        '''
        设置 mem 的数据
        @param key: 键
        '''
        key = "%s_%i" % (key, self.mem_get_ver())
        print 'set:%s' % key
        result = False
        try:
            result = self.cache.set(key, value, timeout)
        except Exception,e:
            print e
            logging.error("Error %s" % str(e),exc_info=True)
        return result

def auto_cache(method):
    '''
    为cps请求设置cache
    '''
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        prefix = method.__name__
        print 'prefix:%s' % prefix
        key_gen,result = {},None
        cache_op = CacheOp(self.cache, prefix)
        refresh = int(self.get_argument('refresh', 0)) #刷新单个请求
        #重启后第一次取值不会从cache中取，需要读一次配置
        cache_conf = key_settings.get(prefix, None)
        if not cache_conf or refresh:
            result,cache_conf = method(self, *args, **kwargs)
            key_settings[prefix] = cache_conf 
            self.send_json(result)
            timeout = cache_conf.get('timeout', 60*60)
            params = cache_conf.get('params', [])
            key_tpl = cache_conf.get('key_tpl', None)
            #params 不能为空，否则会有大批量cache异常
            assert len(params) > 1
            for param in params:
                key_gen[param] = self.get_argument(param, '')
            key = cache_op.make_key(key_gen, key_tpl)
            cache_op.set(key, result, timeout)
            return
        #如果设置过cache_conf,先从cache中获取
        params = cache_conf.get('params', [])
        key_tpl = cache_conf.get('key_tpl', None)
        for param in params:
            key_gen[param] = self.get_argument(param, '')
        key = cache_op.make_key(key_gen, key_tpl)
        result = cache_op.get(key)
        #如果没有命中,回源取数据并设置cache
        if not result:
            result,cache_conf = method(self, *args, **kwargs)
            key_settings[prefix] = cache_conf 
            timeout = cache_conf.get('timeout', 60*60)
            cache_op.set(key, result, timeout)
        self.send_json(result)
    return wrapper

class MainHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.cache = memcache.Client(['localhost:11000']) 

    def get(self, module):
        module = self.parse_module(module)
        method = getattr(self, module or 'index')
        if method and module not in ('get','post'):
            method()
        else:
            raise tornado.web.HTTPError(404)
    
    @auto_cache
    def getSearch(self):
        cache_conf = {'timeout':0, 'params':('a','b'), 'key_tpl':'wlc_%s_%s'}
        cache_conf = {'timeout':0, 'params':('a','b')}
        result = {'status':0, 'msg':'getSearch'}
        return result,cache_conf

    def send_json(self, obj):                                                                                                                        
        ''' 
        输出 JSON
        @author: wangzhongbin
        @param obj: ojbect 输出的对象
        '''
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        if isinstance(obj, str):
            self.write(obj)
        else:
            self.write(json.dumps(obj))

    def parse_module(self, module):
        mod,sub = "",""
        if module:
            arr = module.split("/")
            if len(arr)>=3:
                mod,sub = arr[1],arr[2]
            elif len(arr)>=2:
                mod = arr[1]
        return '%s__%s'%(mod,sub) if sub else mod 

    def get_argument(self, name, default=tornado.web.RequestHandler._ARG_DEFAULT, strip=True):
        '''
        overide it to encode all the param in utf-8
        '''
        value = super(MainHandler,self).get_argument(name,default,strip)
        if not value and default != tornado.web.RequestHandler._ARG_DEFAULT:
            value = default
        if isinstance(value,unicode):
            value = value.encode('utf-8')
        return value

application = tornado.web.Application([
    (r"/test(/[a-zA-Z/]*)?", MainHandler),
])

if __name__ == "__main__":
    application.listen(6656)
    tornado.ioloop.IOLoop.instance().start()
