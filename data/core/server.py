# -*- coding: utf-8 -*-
# data/core/server.py

import json, os, sys, threading
import http.server
import socketserver
import urllib.parse
from data.core.logger import logger
def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

SERVICE_DISPATCHER ={}

def register_service_route (route_name ,handler_func ):
    clean_route =route_name .lower ().strip ("/")
    SERVICE_DISPATCHER [clean_route ]=handler_func

def get_service_handler (route_name ):
    clean_route =route_name .lower ().strip ("/")
    if clean_route in SERVICE_DISPATCHER :
        return SERVICE_DISPATCHER [clean_route ]

    try :
        from data .core .config_manager import config
        active =config .get_str ("SERVICES","ActiveService","google_ai").lower ().strip ()
        if active in SERVICE_DISPATCHER :
            return SERVICE_DISPATCHER [active ]
    except Exception :
        pass

    if SERVICE_DISPATCHER :
        return next (iter (SERVICE_DISPATCHER .values ()))
    return None

class HubRequestHandler (http .server .BaseHTTPRequestHandler ):

    def log_message (self ,format ,*args ):
        pass

    def send_cors_headers (self ):
        self .send_header ('Access-Control-Allow-Origin','*')
        self .send_header ('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self .send_header ('Access-Control-Allow-Headers','Content-Type, Authorization')

    def do_OPTIONS (self ):
        self .send_response (200 )
        self .send_cors_headers ()
        self .send_header ('Content-Length','0')
        self .end_headers ()

    def do_GET (self ):
        parsed =urllib .parse .urlparse (self .path )
        path =parsed .path .lower ().strip ("/")

        if path ==""or path =="status":
            out =json .dumps ({"status":"running","services":list (SERVICE_DISPATCHER .keys ())}).encode ("utf-8")
            self .send_response (200 )
            self .send_header ('Content-Type','application/json; charset=utf-8')
            self .send_header ('Content-Length',str (len (out )))
            self .send_cors_headers ()
            self .end_headers ()
            self .wfile .write (out )
            return

        if path =="tts":
            handler =get_service_handler ("tts")
            if handler :
                params =urllib .parse .parse_qs (parsed .query )
                text =params .get ("text",[""])[0 ]
                lang =params .get ("lang",["ru"])[0 ]
                audio_bytes =handler (text =text ,lang =lang )
                if audio_bytes :
                    self .send_response (200 )
                    self .send_header ('Content-Type','audio/mpeg')
                    self .send_header ('Content-Length',str (len (audio_bytes )))
                    self .send_cors_headers ()
                    self .end_headers ()
                    self .wfile .write (audio_bytes )
                    return

        self .send_response (404 )
        self .end_headers ()

    def do_POST (self ):
        try :
            content_len =int (self .headers .get ('Content-Length',0 ))
            raw_body =self .rfile .read (content_len ).decode ('utf-8',errors ='ignore')

            try :
                body =json .loads (raw_body )
            except Exception :
                body ={"text":raw_body }

            parsed =urllib .parse .urlparse (self .path )
            route =parsed .path
            req_text =body .get ("text","")
            src_lang =body .get ("from","auto")
            trg_lang =body .get ("to","ru")
            preset_val =body .get ("preset",None )

            logger .qtranslate_request (route ,src_lang ,trg_lang ,req_text )

            handler =get_service_handler (route )

            if handler :
                result_text =handler (
                text =req_text ,
                src_lang =src_lang ,
                trg_lang =trg_lang ,
                preset =preset_val
                )
                out_data ={"response":result_text ,"success":True }
            else :
                err_msg =f"[AI Hub]: Text '{route }' Text Text Text Text Text Text."
                logger .system (err_msg )
                out_data ={
                "response":err_msg ,
                "success":False
                }

            out_bytes =json .dumps (out_data ,ensure_ascii =False ).encode ('utf-8')

            self .send_response (200 )
            self .send_header ('Content-Type','application/json; charset=utf-8')
            self .send_header ('Content-Length',str (len (out_bytes )))
            self .send_header ('Connection','close')
            self .send_cors_headers ()
            self .end_headers ()
            self .wfile .write (out_bytes )

        except (ConnectionAbortedError ,ConnectionResetError ):
            pass
        except Exception as e :
            logger .system (f"Error Text HubRequestHandler.do_POST: {e }")
            err_bytes =json .dumps ({"response":f"Error Text: {e }","success":False },ensure_ascii =False ).encode ('utf-8')
            try :
                self .send_response (500 )
                self .send_header ('Content-Type','application/json; charset=utf-8')
                self .send_header ('Content-Length',str (len (err_bytes )))
                self .send_cors_headers ()
                self .end_headers ()
                self .wfile .write (err_bytes )
            except Exception :
                pass

class ThreadedHTTPServer (socketserver .ThreadingMixIn ,http .server .HTTPServer ):
    allow_reuse_address =True
    daemon_threads =True

_server_instance =None
_server_thread =None

def start_server (port =8080 ,block =False ):
    global _server_instance ,_server_thread

    if _server_instance :
        return

    try :
        from data .core .config_manager import config
        port =config .get_int ("GENERAL","ServerPort",port )
    except Exception :
        pass

    _server_instance =ThreadedHTTPServer (('127.0.0.1',port ),HubRequestHandler )
    print (f"[HTTP Server]: Text Text Text http://127.0.0.1:{port }")
    logger .system (f"HTTP-Text Text Text 127.0.0.1:{port }")

    if block :
        try :
            _server_instance .serve_forever ()
        except KeyboardInterrupt :
            stop_server ()
    else :
        _server_thread =threading .Thread (target =_server_instance .serve_forever ,daemon =True )
        _server_thread .start ()

def stop_server ():
    global _server_instance
    if _server_instance :
        try :
            _server_instance .shutdown ()
            _server_instance .server_close ()
        except Exception :
            pass
        _server_instance =None
        print ("[HTTP Server]: Server stopped.")
        logger .system ("HTTP-Text Text")
