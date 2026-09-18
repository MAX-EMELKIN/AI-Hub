# -*- coding: utf-8 -*-
# data/batch/code_protector.py

import re
class CodeProtector :

    def __init__ (self ):

        self .patterns =[

        r'```[\s\S]*?```',

        r'`[^`\r\n]+`',

        r'https?://[^\s<>"\)\]]+',

        r'</?[A-Za-z0-9_]+(?:\s*=\s*[^>]+)?>',

        r'%[0-9]*\.?[0-9]*[sdifoxXb]',
        r'\{[0-9A-Za-z_$\.\-]+\}',
        r'\$[A-Za-z_][A-Za-z0-9_]*',

        r'\\[nrt]'
        ]
        self .master_regex =re .compile ('|'.join (f'({p })'for p in self .patterns ))

    def mask (self ,text ):
        if not text :
            return text ,{}

        tokens ={}
        token_counter =1

        def _replacer (match ):
            nonlocal token_counter
            matched_str =match .group (0 )
            token_name =f"[[__CODE_{token_counter :03d}__]]"
            tokens [token_name ]=matched_str
            token_counter +=1
            return token_name

        masked_text =self .master_regex .sub (_replacer ,text )
        return masked_text ,tokens

    def restore (self ,translated_text ,tokens ):
        if not translated_text or not tokens :
            return translated_text

        restored_text =translated_text

        for token_name ,original_val in tokens .items ():

            raw_id =token_name .strip ("[]")

            flexible_pattern =r'\[\s*\[\s*'+re .escape (raw_id )+r'\s*\]\s*\]'

            if re .search (flexible_pattern ,restored_text ):
                restored_text =re .sub (flexible_pattern ,lambda _ :original_val ,restored_text )
            else :

                restored_text =restored_text .replace (token_name ,original_val )

        return restored_text

code_protector =CodeProtector ()
