import os
import json
import re
import time
from collections import OrderedDict
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source='en', target='es')

PROTECT_REGEX = re.compile(r'(§[0-9a-fk-or]|%[0-9]*\$?[sfd]|\$\([^)]+\)|<[^>]+>|\{[0-9]+\})')

def protect_string(text):
    matches = PROTECT_REGEX.findall(text)
    protected_text = text
    for i, match in enumerate(matches):
        protected_text = protected_text.replace(match, f' X{i}X ')
    return protected_text, matches

def unprotect_string(text, matches):
    for i, match in enumerate(matches):
        text = text.replace(f'X{i}X', match)
        text = text.replace(f' {match} ', match)
        text = text.replace(f' {match}', match)
        text = text.replace(f'{match} ', match)
    return text

def should_skip(key):
    k = key.lower()
    if 'itemgroup' in k or 'key.categories' in k or 'category' in k:
        return True
    return False

def translate_batch(strings):
    if not strings:
        return []
    
    SEPARATOR = ' ||| '
    
    protected_data = []
    for s in strings:
        if not s.strip():
            protected_data.append([(s, [])])
        else:
            parts = s.split('\n')
            parts_protected = [protect_string(p) if p.strip() else (p, []) for p in parts]
            protected_data.append(parts_protected)
            
    to_translate = []
    for item in protected_data:
        for p_text, matches in item:
            if p_text.strip():
                to_translate.append(p_text)
                
    CHUNK_SIZE = 20
    translated_texts = {}
    
    for i in range(0, len(to_translate), CHUNK_SIZE):
        chunk = to_translate[i:i+CHUNK_SIZE]
        if not chunk: continue
        combined = SEPARATOR.join(chunk)
        try:
            res = translator.translate(combined)
            res_parts = res.split(SEPARATOR)
            if len(res_parts) != len(chunk):
                # fallback
                for text in chunk:
                    try:
                        translated_texts[text] = translator.translate(text)
                    except:
                        translated_texts[text] = text
                    time.sleep(0.1)
            else:
                for orig, trans in zip(chunk, res_parts):
                    translated_texts[orig] = trans
        except Exception as e:
            print(f"Error in batch translation: {e}")
            for text in chunk:
                translated_texts[text] = text
        time.sleep(0.3)
        
    final_results = []
    for item in protected_data:
        final_parts = []
        for p_text, matches in item:
            if not p_text.strip():
                final_parts.append(p_text)
            else:
                t_text = translated_texts.get(p_text, p_text)
                final_parts.append(unprotect_string(t_text, matches))
        final_results.append('\n'.join(final_parts))
        
    return final_results

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f, object_pairs_hook=OrderedDict)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

assets_dir = r'f:\Github\HL-Project\assets'
mods = sorted([d for d in os.listdir(assets_dir) if os.path.isdir(os.path.join(assets_dir, d))])

summary = []

for mod in mods:
    lang_dir = os.path.join(assets_dir, mod, 'lang')
    en_path = os.path.join(lang_dir, 'en_us.json')
    if not os.path.exists(en_path):
        continue
        
    try:
        en_data = load_json(en_path)
    except Exception as e:
        print(f"Error reading {en_path}: {e}")
        continue
        
    es_path = os.path.join(lang_dir, 'es_es.json')
    es_data = OrderedDict()
    
    caso = 3
    fuente_caso_2 = None
    
    if os.path.exists(es_path):
        caso = 1
        try:
            es_data = load_json(es_path)
        except:
            pass
    else:
        for tmp in ['tmp_es.json', 'tmp_mx.json', 'tmp_ar.json']:
            tmp_path = os.path.join(lang_dir, tmp)
            if os.path.exists(tmp_path):
                caso = 2
                fuente_caso_2 = tmp
                try:
                    es_data = load_json(tmp_path)
                except:
                    pass
                break
                
    missing_keys = []
    for k, v in en_data.items():
        if k not in es_data:
            missing_keys.append((k, v))
            
    if missing_keys:
        print(f"Mod {mod}: faltan {len(missing_keys)} claves. (Caso {caso})")
        
        keys_to_translate = []
        strings_to_translate = []
        
        for k, v in missing_keys:
            if should_skip(k):
                pass
            else:
                keys_to_translate.append(k)
                if isinstance(v, str):
                    strings_to_translate.append(v)
                else:
                    strings_to_translate.append(str(v))
                
        print(f" -> Traduciendo {len(strings_to_translate)} strings...")
        translated_strings = translate_batch(strings_to_translate)
        
        translation_map = dict(zip(keys_to_translate, translated_strings))
        
        new_es_data = OrderedDict()
        added_count = 0
        
        for k, v in en_data.items():
            if k in es_data:
                new_es_data[k] = es_data[k]
            else:
                if should_skip(k):
                    new_es_data[k] = v
                else:
                    new_es_data[k] = translation_map[k]
                added_count += 1
                
        for k in es_data:
            if k not in new_es_data:
                new_es_data[k] = es_data[k]
                
        os.makedirs(lang_dir, exist_ok=True)
        save_json(es_path, new_es_data)
        
    else:
        added_count = 0
        
    if caso == 1:
        accion = "Actualizado es_es.json"
    elif caso == 2:
        accion = f"Creado es_es.json basado en {fuente_caso_2} y actualizado"
    else:
        accion = "Creado es_es.json desde cero"
        
    if added_count == 0:
        if caso == 1:
            claves_str = "0 (completamente actualizado)"
        else:
            claves_str = "0"
    else:
        if caso == 3 and added_count == len(en_data):
            claves_str = f"N/A — traducción completa ({added_count} claves)"
        else:
            claves_str = str(added_count)
            
    res_str = f"**MOD:** {mod}\n**CASO:** {caso} {f'(fuente: {fuente_caso_2})' if fuente_caso_2 else ''}\n**CLAVES FALTANTES:** {claves_str}\n**ACCIÓN:** {accion}\n"
    summary.append(res_str)

with open(r'C:\Users\hecto\.gemini\antigravity\brain\eb147d56-8ced-476c-a6db-af8cc7db48a6\summary.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(summary))

print("Proceso completado exitosamente.")
