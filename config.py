#!/usr/bin/python3
import argparse, os, struct, json, mmap, itertools, copy
import regex as re


types_list_2 = ['INTEGER PRIMARY KEY', 'INTEGER', 'INTEGER NOT NULL', 'BOOLEAN', 'BOOLEAN NOT NULL', 'REAL', 'REAL NOT NULL', 
'TEXT', 'TEXT NOT NULL', 'NUMERIC', 'NUMERIC NOT NULL', 'BLOB', 'BLOB NOT NULL']

types_affinities = {'(INTEGER PRIMARY KEY)':'INTEGER PRIMARY KEY', '((INT|DATE)(?!.*NO.*NULL)(?!.*PRIMARY.*KEY))':'INTEGER', 
'((INT|DATE)(.*NO.*NULL))':'INTEGER NOT NULL', '(BOOL(?!.*NO.*NULL))':'BOOLEAN', '(BOOL.*NO.*NULL)':'BOOLEAN NOT NULL', 
'((CHAR|TEXT|CLOB)(?!.*NO.*NULL))':'TEXT', '((CHAR|TEXT|CLOB)(.*NO.*NULL))':'TEXT NOT NULL', '(BLOB(?!.*NO.*NULL))':'BLOB', 
'(BLOB.*NO.*NULL)':'BLOB NOT NULL', '((REAL|DOUB|FLOA)(?!.*NO.*NULL))':'REAL', '((REAL|DOUB|FLOA)(.*NO.*NULL))':'REAL NOT NULL', 
'((NUMERIC|JSON|GUID|UUID)(?!.*NO.*NULL))':'NUMERIC', '((NUMERIC|JSON)(.*NO.*NULL))':'NUMERIC NOT NULL'}


#To sum elements in list
def somme(liste):
    _somme = 0
    for i in liste:
        _somme = _somme + i
    return _somme



#To decode Huffman coding
def huffmanEncoding(x,y):
    x = int(x)
    z = (x-128)*128
    a = z + int(y)
    return(hex(a))



#SQLite serial types translation
def serialTypes(serial_type):
    _serial_type = 0
    if serial_type == 5:
        _serial_type = 6
    elif serial_type == 6:
        _serial_type = 8
    elif serial_type == 7:
        _serial_type = 8
    elif serial_type == 8:
        _serial_type = 0
    elif serial_type == 9:
        _serial_type = 0
    elif serial_type >= 12 and serial_type % 2 == 0:
        _serial_type = round((serial_type-12)/2)
    elif serial_type >= 13 and serial_type % 2 != 0:
        _serial_type = round((serial_type-13)/2)
    else:
        _serial_type = serial_type
    return _serial_type




#Function that decodes bytes from possible header into integers (so that we can do calculations on it after) and appends them to unknown_header list
def decode_unknown_header(unknown_header, a, b, limit, len_start_header, freeblock:bool):
    #WITH ROWID
    count = 0
    #While not end of the match
    while count <= (b-a-1):
        #If [payload length, rowid, types length] part --> not serial types so just append(byte) and not append(serialTypes(byte))
        if len(unknown_header) < len_start_header:
            #If it's a freeblock, read 2 bytes then 2 bytes
            if freeblock:
                byte = int(struct.unpack('>H', file.read(2))[0])
                unknown_header.append(byte)
                count+=2
            else:
                #Read byte by byte, convert in int, and append to unknown_header list
                byte = int(struct.unpack('>B', file.read(1))[0])
                if byte < 128:
                    unknown_header.append(byte)
                    count+=1
                #Deal with Huffman coding until 9 successive bytes > 0x80 or > 128
                else:
                    cont1 = int(struct.unpack('>B', file.read(1))[0])
                    byte1 = int(huffmanEncoding(byte, cont1),16)
                    if cont1 < 128:
                        unknown_header.append(byte1)
                        count+=2
                    else:
                        cont2 = int(struct.unpack('>B', file.read(1))[0])
                        byte2 = int(huffmanEncoding(byte1, cont2),16)
                        count+=2
                        if cont2 < 128:
                            unknown_header.append(byte2)
                            count+=1
                        else:
                            count+=1
                            cont3 = int(struct.unpack('>B', file.read(1))[0])
                            byte3 = int(huffmanEncoding(byte2, cont3),16)
                            if cont3 < 128:
                                unknown_header.append(byte3)
                                count+=1
                            else:
                                count+=1
                                cont4 = int(struct.unpack('>B', file.read(1))[0])
                                byte4 = int(huffmanEncoding(byte3, cont4),16)
                                if cont4 < 128:
                                    unknown_header.append(byte4)
                                    count+=1
                                else:
                                    count+=1
                                    cont5 = int(struct.unpack('>B', file.read(1))[0])
                                    byte5 = int(huffmanEncoding(byte4, cont5),16)
                                    if cont5 < 128:
                                        unknown_header.append(byte5)
                                        count+=1
                                    else:
                                        count+=1
                                        cont6 = int(struct.unpack('>B', file.read(1))[0])
                                        byte6 = int(huffmanEncoding(byte5, cont6),16)
                                        if cont6 < 128:
                                            unknown_header.append(byte6)
                                            count+=1
                                        else:
                                            count+=1
                                            cont7 = int(struct.unpack('>B', file.read(1))[0])
                                            byte7 = int(huffmanEncoding(byte6, cont7),16)
                                            if cont7 < 128:
                                                unknown_header.append(byte7)
                                                count+=1
                                            else:
                                                count+=1
                                                cont8 = int(struct.unpack('>B', file.read(1))[0])
                                                byte8 = int(huffmanEncoding(byte7, cont8),16)
                                                if cont8 < 128:
                                                    unknown_header.append(byte8)
                                                    count+=1
                                                else:
                                                    count+=1
                                                    cont9 = int(struct.unpack('>B', file.read(1))[0])
                                                    byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                    unknown_header.append(byte9)
        
        #If [types] part --> type1, type2, etc. --> append(serialTypes(byte))
        else:
            #list limit to know how many bytes takes start of header (because 3 integers not necessarily only 3 bytes)
            limit.append(count)
            byte = int(struct.unpack('>B', file.read(1))[0])
            if byte < 128:
                unknown_header.append(serialTypes(byte))
                count+=1
            #Deal with Huffman coding until 9 successive bytes > 0x80 or > 128
            else:
                cont1 = int(struct.unpack('>B', file.read(1))[0])
                byte1 = int(huffmanEncoding(byte, cont1),16)
                if cont1 < 128:
                    unknown_header.append(serialTypes(byte1))
                    count+=2
                else:
                    cont2 = int(struct.unpack('>B', file.read(1))[0])
                    byte2 = int(huffmanEncoding(byte1, cont2),16)
                    count+=2
                    if cont2 < 128:
                        unknown_header.append(serialTypes(byte2))
                        count+=1
                    else:
                        count+=1
                        cont3 = int(struct.unpack('>B', file.read(1))[0])
                        byte3 = int(huffmanEncoding(byte2, cont3),16)
                        if cont3 < 128:
                            unknown_header.append(serialTypes(byte3))
                            count+=1
                        else:
                            count+=1
                            cont4 = int(struct.unpack('>B', file.read(1))[0])
                            byte4 = int(huffmanEncoding(byte3, cont4),16)
                            if cont4 < 128:
                                unknown_header.append(serialTypes(byte4))
                                count+=1
                            else:
                                count+=1
                                cont5 = int(struct.unpack('>B', file.read(1))[0])
                                byte5 = int(huffmanEncoding(byte4, cont5),16)
                                if cont5 < 128:
                                    unknown_header.append(serialTypes(byte5))
                                    count+=1
                                else:
                                    count+=1
                                    cont6 = int(struct.unpack('>B', file.read(1))[0])
                                    byte6 = int(huffmanEncoding(byte5, cont6),16)
                                    if cont6 < 128:
                                        unknown_header.append(serialTypes(byte6))
                                        count+=1
                                    else:
                                        count+=1
                                        cont7 = int(struct.unpack('>B', file.read(1))[0])
                                        byte7 = int(huffmanEncoding(byte6, cont7),16)
                                        if cont7 < 128:
                                            unknown_header.append(serialTypes(byte7))
                                            count+=1
                                        else:
                                            count+=1
                                            cont8 = int(struct.unpack('>B', file.read(1))[0])
                                            byte8 = int(huffmanEncoding(byte7, cont8),16)
                                            if cont8 < 128:
                                                unknown_header.append(serialTypes(byte8))
                                                count+=1
                                            else:
                                                count+=1
                                                cont9 = int(struct.unpack('>B', file.read(1))[0])
                                                byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                unknown_header.append(serialTypes(byte9))

    #Return possible headers without filtering on payload length = sum of types, return limit to know number of start header bytes
    return unknown_header, limit



def default_table(dictionary, name):
    for dictionaries in dictionary:
        for key2,value2 in dictionaries.items():
            list_values = list(value2.values())
            list_keys = list(value2.keys())

            if 'DEFAULT' in list_values[-1] and len(list_values) > 5:
                default_dict = copy.deepcopy(dictionaries)
                for key,value in default_dict.items():
                    value.pop(list_keys[-1])
                    element = str(key) + str(name)
                    keys_default[key] = element
                
                for key,value in default_dict.copy().items():
                    for key1,value1 in keys_default.items():
                        if key == key1:
                            default_dict[value1] = default_dict[key]
                            del default_dict[key]
                
                config.append(default_dict)
         


parser = argparse.ArgumentParser()
parser.add_argument("--filename", nargs='+')
args = parser.parse_args()


db_files = []
db_paths = []
for file_name in args.filename:
    if os.path.isdir(file_name):
        for parent, dirnames, filenames in os.walk(file_name):
            for fn in filenames:
                filepath = os.path.join(parent, fn)
                if fn.endswith(".sqlite") or fn.endswith(".sqlite3") or fn.endswith(".db") or fn.endswith(".db3"):
                    db_files.append(fn)
                    db_paths.append(filepath)
    elif os.path.isfile(file_name):
        db_files.append(file_name)
    else:
        print("Nor file nor directory")

for db_file in db_files:
    if os.path.isdir(file_name):
        index = db_files.index(db_file)
        open_file = db_paths[index]
    else:
        open_file = db_file
    #Open db file to add to config.py
    with open(open_file, 'r+b') as file:
        size = os.path.getsize(open_file)
        file_name, extension = os.path.splitext(open_file)
        file_name = db_file.replace(extension, '')
        
        file.seek(0)

        #Read 16 for the SQLite format 3 signature
        signature = file.read(15)
        
        if signature != b'\x53\x51\x4C\x69\x74\x65\x20\x66\x6F\x72\x6D\x61\x74\x20\x33':
            print("Not a sqlite 3 database")
        
        else:
            file.read(1)
            
            db_infos = {}
            db_info = []
            db_infos["file name"] = file_name
            #Retrieve all header information and put it into list then into dict
            page_size = int(struct.unpack('>H', file.read(2))[0]) #here x10 x00 = 4096
            db_infos["page size"] = page_size

            file_format_w = int(struct.unpack('>B', file.read(1))[0]) #here x01 = RJ
            db_infos["write version"] = file_format_w

            file_format_r = int(struct.unpack('>B', file.read(1))[0]) #here x01 = RJ
            db_infos["read version"] = file_format_r

            reserved_bytes = int(struct.unpack('>B', file.read(1))[0])
            db_infos["reserved bytes"] = reserved_bytes

            file.read(3)

            file_change_counter = int(struct.unpack('>i', file.read(4))[0])
            db_infos["database updates"] = file_change_counter

            number_pages = int(struct.unpack('>i', file.read(4))[0])
            db_infos["number of pages"] = number_pages

            db_size = int(page_size) * int(number_pages)
            db_infos["database size"] = db_size

            file.read(8)

            schema_cookie = int(struct.unpack('>i', file.read(4))[0]) 
            db_infos["schema changes"] = schema_cookie

            file.read(12)

            text_encoding = int(struct.unpack('>i', file.read(4))[0]) #here 1 = UTF-8
            db_infos["text encoding"] = text_encoding

            file.read(36)

            sqlite_version = int(struct.unpack('>i', file.read(4))[0]) #here 3.31.0
            db_infos["sqlite version"] = sqlite_version



            #Config file is an array
            config = []
            #Append list with dict of db header information to config file
            config.append(db_infos)




            regex = rb'(([\x03-\x80]{1})|([\x81-\xff]{1,8}[\x00-\x80]{1}))(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1}))(([\x02-\x80]{1})|([\x81-\xff]{1,8}[\x00-\x80]{1}))([\x17]{1})(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1}))(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1}))([\x00-\x09]{1})(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1}))'
            regex = re.compile(regex)
            mm = mmap.mmap(file.fileno(), 0)
            for match in re.finditer(regex, mm, overlapped=True):
                unknown_header = []
                limit = []
                a = match.start()
                b = match.end()

                #Go to start of the match
                file.seek(a)

                decode_unknown_header(unknown_header, a, b, limit, len_start_header=3, freeblock=False)
                

                payload = []
                #Filter: if we have at least a payload length, rowid, types length and 1 type AND that payload length = sum of types and serial types array AND types not all = 0
                if ((unknown_header[0] == somme(unknown_header[2:]))) and (somme(unknown_header[3:]) != 0) and (b-a-limit[0]+1 == unknown_header[2]):
                    #Go to the end of the match to start reading payload content
                    file.seek(b)
                    #For each length of each type
                    for l in ((unknown_header)[3:]):
                        #Read bytes for that length and decode it according to encoding : e.g. [48, 42, 8, 0, 24, 7, 1, 0, 8, 0] --> read following number of bytes [0, 24, 7, 1, 0, 8, 0]
                        payload_field = file.read(l).decode('utf-8', errors='ignore')
                        #Decode simple 1-byte integers
                        try:
                            payload_field = ord(payload_field)
                        except:
                            payload_field = payload_field
                        #Append to payload content list : e.g. [0, 24, 7, 1, 0, 8, 0] --> ['', 'https://www.youtube.com/', 'YouTube', 3, '', 13263172804027223, '']
                        payload.append(payload_field)



                    if payload[0] == 'table' and ('CREATE TABLE' or 'create table' in payload[4]) and ('sqlite_' not in payload[4]):
                        #Continue completing config.json with table/fields information
                        table_name = payload[1]
                        #Corpus 01-18.db
                        for i in table_name:
                            if ord(i) <= 20:
                                table_name = table_name.replace(i, 'character_before_20')
                        #Corpus 01-13.db
                        if payload[1] == 40:
                            fields = payload[4].split('(',2)[2]
                        else:
                            fields = payload[4].split('(',1)[1]

                        #Corpus 01-all special characters cases
                        if type(table_name) == int:
                            table_name = 'special_character_' + str(table_name)

                        #Clean table name
                        if table_name.startswith("'") and table_name.endswith("'"):
                            table_name = table_name[1:-1]
                            #Corpus 01-01.db
                            if table_name == '':
                                table_name = '\'\''
                        if table_name.startswith('"') and table_name.endswith('"'):
                            table_name = table_name[1:-1]
                            #Corpus 01-01.db
                            if table_name == '':
                                table_name = '\"\"'
                        # if table_name.startswith('[') and table_name.endswith(']'):
                        #     table_name = table_name[1:-1]
                            #Corpus 01-01.db
                            if table_name == '':
                                table_name = '[]'
                        
                        #Corpus 01-02.db
                        table_name = table_name.replace("'", "apostrophe_exception_name")
                        table_name = table_name.replace('"', "quotation_exception_name")
                        table_name = table_name.replace('--', "double_dash_exception_name")
                        table_name = table_name.replace('%s', "parameterized_string_exception_name")
                        if table_name == '':
                            table_name = '\"\"'

                        
                        #Clean fields
                        if fields.endswith(' )'):
                            fields = fields[:-2]
                        if fields.endswith(')'):
                            fields = fields[:-1]    

                        fields = re.sub(r'(PRIMARY KEY){1}( )*\({1}.+', '', fields)
                        fields = re.sub(r'(UNIQUE){1}( )*\({1}.+', '', fields)
                        fields = re.sub(r'(FOREIGN KEY){1}( )*\({1}.+', '', fields)
                        fields = re.sub(r'(CHECK){1}( )*\({1}.+', '', fields)
                        fields = re.sub(r'(REFERENCES ){1}.*', '', fields)
                        fields = re.sub(r'(CONSTRAINT ){1}.*', '', fields)


                        if fields.endswith(','):
                            fields = fields[:-1]

                        #Fields are separated by commas
                        fields = fields.split(',')

                        #Put table name and each associated field in same list
                        field_list_config = []


                        #Make a dictionary for each field, name:type
                        #The type is one of the types in serial_types_list
                        for i in fields:
                            #Cleaning again
                            if i.startswith('\n\t'):
                                i = i[1:]
                            if i.startswith('\n\\'):
                                i = i[2:]
                            if i.startswith(' '):
                                i = i[1:]
                            i = i.replace('\t', ' ')
                            i = i.replace('\n', '')
                            i = i.replace('\\', '')
                            if i.startswith(' "'):
                                i = i[2:]
                            
                            if i.startswith('   '):
                                i = i[3:]

                            if i.startswith('  '):
                                i = i[2:]

                            if i.startswith(' '):
                                i = i[1:]
                            
                            #Separate name and type by first space...
                            _name_ = i.partition(' ')
                            if _name_[0] == '':
                                _name_ = i.partition(' ')

                            name_ = _name_[0]
                            type_ = _name_[2]

                            
                            if name_.startswith("'") and name_.endswith("'"):
                                name_ = name_[1:-1]
                            if name_.startswith('"') and name_.endswith('"'):
                                name_ = name_[1:-1]
                            # if name_.startswith('[') and name_.endswith(']'):
                            #     name_ = name_[1:-1]
                            if name_.endswith(' "'):
                                name_ = name_[:-2]
                            # if name_.endswith('"') or name_.endswith(']'):
                            #     name_ = name_[:-1]

                                                
                            if (name_ == '' and type_ == '') or (name_ == "\n" and type_ == "") or (name_ == "" and type_ == " ") or (name_ == "" and type_ == "  "):
                                pass
                            else:
                                if type_ == '':
                                    type_ = 'NUMERIC'
                                for key,value in types_affinities.items():
                                    if 'DEFAULT' not in type_:
                                        type_ = re.sub(rf'.*{key}.*', value, type_, flags=re.IGNORECASE)
                                    else:
                                        type_ = re.sub(rf'.*{key}.*', value + ' DEFAULT 0', type_, flags=re.IGNORECASE)

                                if type_ not in types_list_2 and 'DEFAULT' not in type_:
                                    if 'NOT NULL' in type_:
                                        type_ = 'NUMERIC NOT NULL'
                                    else:
                                        type_ = 'NUMERIC'
                                
                                field_list_config.append(name_)
                                field_list_config.append(type_)
                        
                        
                        dict_transf_config = {field_list_config[i]: field_list_config[i + 1] for i in range(0, len(field_list_config), 2)}
                    
                        fields_lists_config = {table_name:dict_transf_config}

                        #Append list with table_name, fields to config file
                        if fields_lists_config not in config:
                            config.append(fields_lists_config)


            keys_copies = {}
            for a,b in itertools.combinations(config[1:],2):
                if a.keys() == b.keys():
                    for key,value in b.items():
                        element = str(key) + '_copy'
                        keys_copies[key] = element
            
            for a,b in itertools.combinations(config[1:],2):
                if a.keys() == b.keys():
                    for key,value in keys_copies.items():
                        for key1,value1 in b.copy().items():
                            if key == key1:
                                b[value] = b[key1]
                                del b[key]
            
            keys_default = {}


            #Default case
            name = 0
            z = 1
            x = len(config)
            default_table(config[z:], name)
            name+=1
            default_table(config[x-z:], name)
            
            
            while True:
                name+=1
                y = len(config)
                default_table(config[y-z:], name)
                w = len(config)
                if w==y:
                    break
                else:
                    continue

            
            #Create new db if already exists
            output_config = "config_%s.json" % file_name
            
            #Write config array in a json file
            with open (output_config, 'w') as config_file:
                json.dump(config, config_file, indent=2)
            config_file.close()
            

            #Free the memory
            mm.close()
    
    
    #Close the db file
    file.close()
