# -*- coding: utf-8 -*-
# data/batch/chunker.py

import os, re
class TextChunker :

    def __init__ (self ,default_chunk_size =2500 ):
        self .default_chunk_size =default_chunk_size

    def read_file_safe (self ,file_path ):
        if not os .path .exists (file_path ):
            raise FileNotFoundError (f"Файл не найден: {file_path }")

        encodings_to_try =["utf-8-sig","utf-8","cp1251","windows-1252","utf-16","cp866"]
        for enc in encodings_to_try :
            try :
                with open (file_path ,"r",encoding =enc )as f :
                    content =f .read ()
                    return content ,enc
            except (UnicodeDecodeError ,UnicodeError ):
                continue

        with open (file_path ,"r",encoding ="utf-8",errors ="ignore")as f :
            return f .read (),"utf-8 (fallback)"

    def write_file_safe (self ,file_path ,content ,encoding ="utf-8"):
        out_dir =os .path .dirname (file_path )
        if out_dir :
            os .makedirs (out_dir ,exist_ok =True )

        with open (file_path ,"w",encoding =encoding ,errors ="replace")as f :
            f .write (content )

    def _split_long_paragraph (self ,paragraph ,max_size ):

        if '\n'in paragraph :
            lines =paragraph .split ('\n')
            result_chunks =[]
            current_lines =[]
            current_len =0

            for line in lines :
                line_len =len (line )+1
                if current_len +line_len >max_size and current_lines :
                    result_chunks .append ("\n".join (current_lines ))
                    current_lines =[line ]
                    current_len =line_len
                else :
                    current_lines .append (line )
                    current_len +=line_len

            if current_lines :
                result_chunks .append ("\n".join (current_lines ))
            return result_chunks

        sentence_end_pattern =re .compile (r'(?<=[.!?…])\s+')
        sentences =sentence_end_pattern .split (paragraph )

        result_chunks =[]
        current_chunk =[]
        current_len =0

        for sentence in sentences :
            sentence =sentence .strip ()
            if not sentence :continue

            if len (sentence )>max_size :
                words =sentence .split ()
                sub_chunk =[]
                sub_len =0
                for w in words :
                    if sub_len +len (w )+1 >max_size and sub_chunk :
                        result_chunks .append (" ".join (sub_chunk ))
                        sub_chunk =[w ]
                        sub_len =len (w )
                    else :
                        sub_chunk .append (w )
                        sub_len +=len (w )+1
                if sub_chunk :
                    result_chunks .append (" ".join (sub_chunk ))
                continue

            if current_len +len (sentence )+1 >max_size and current_chunk :
                result_chunks .append (" ".join (current_chunk ))
                current_chunk =[sentence ]
                current_len =len (sentence )
            else :
                current_chunk .append (sentence )
                current_len +=len (sentence )+1

        if current_chunk :
            result_chunks .append (" ".join (current_chunk ))

        return result_chunks

    def split_into_chunks (self ,text ,chunk_size =None ):
        if not text or not text .strip ():
            return []

        if chunk_size is None :
            try :
                from data .core .config_manager import config
                chunk_size =config .get_int ("BATCH","ChunkSize",self .default_chunk_size )
            except Exception :
                chunk_size =self .default_chunk_size

        normalized_text =text .replace ('\r\n','\n').replace ('\r','\n')
        paragraphs =normalized_text .split ('\n\n')

        final_chunks =[]
        current_block =[]
        current_block_len =0

        for p in paragraphs :
            p_clean =p .strip ()
            if not p_clean :continue

            if len (p )>chunk_size :
                if current_block :
                    final_chunks .append ("\n\n".join (current_block ))
                    current_block =[]
                    current_block_len =0

                sub_parts =self ._split_long_paragraph (p ,chunk_size )
                final_chunks .extend (sub_parts )
                continue

            if current_block_len +len (p )+2 >chunk_size and current_block :
                final_chunks .append ("\n\n".join (current_block ))
                current_block =[p ]
                current_block_len =len (p )
            else :
                current_block .append (p )
                current_block_len +=len (p )+2

        if current_block :
            final_chunks .append ("\n\n".join (current_block ))

        return final_chunks

    def assemble (self ,translated_chunks ):
        if not translated_chunks :
            return ""
        return "\n\n".join (chunk .strip ()for chunk in translated_chunks if chunk and chunk .strip ())

text_chunker =TextChunker ()
