#!/usr/bin/python3
import argparse, os, sys, struct, json, mmap, sqlite3, string
import regex as re



#Regexes for types
zero = r'([\x00]{1})'

integer = r'(([\x00-\x06]|[\x08-\x09]){1})'
integer_not_null = r'(([\x01-\x06]|[\x08-\x09]){1})'

boolean = r'(([\x00]|[\x08]|[\x09]){1})'
boolean_not_null = r'(([\x08]|[\x09]){1})'

real = r'(([\x00]|[\x07]){1})'
real_not_null = r'([\x07]{1})'

text = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00]{1})|([\x0d-\x80]{1}))'
text_not_null = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x0d-\x80]{1}))'

numeric = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00]{1})|([\x00-\x80]{1}))'
numeric_not_null = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1}))'

blob = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00]{1})|([\x0c-\x80]{1}))'
blob_not_null = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x0c-\x80]{1}))'


#Regexes payload content
nothing = r''
strings = r'((?<=[\x20-\xff])*)'
strings_not_null = r'((?<=[\x20-\xff])+)'
numbers = r'((?<=[\x00-\xff]){0,9})'
numbers_not_null = r'((?<=[\x00-\xff]){1,9})'
floating = r'((?<=\'\')|(?<=[\x00-\xff]){8})'
floating_not_null = r'((?<=[\x00-\xff]){8})'
everything = r'(^(?!.+\x00{10,}.+)(?<=[\x00-\xff])*)'
everything_not_null = r'(^(?!.+\x00{10,}.+)(?<=[\x00-\xff])+)'


types_list = ['zero', 'integer', 'integer_not_null', 'boolean', 'boolean_not_null', 'real', 'real_not_null', 'text', 'text_not_null', 'numeric', 'numeric_not_null', 'blob', 'blob_not_null']

types_sub = {'(INTEGER PRIMARY KEY)':'zero', '((INT|DATE)(?!.*NO.*NULL))':'integer', '((INT|DATE)(.*NO.*NULL))':'integer_not_null', 
'(BOOL(?!.*NO.*NULL))':'boolean', '(BOOL.*NO.*NULL)':'boolean_not_null', '((CHAR|TEXT|CLOB)(?!.*NO.*NULL))':'text', 
'((CHAR|TEXT|CLOB)(.*NO.*NULL))':'text_not_null', '(BLOB(?!.*NO.*NULL))':'blob', '(BLOB.*NO.*NULL)':'blob_not_null',
'((REAL|DOUB|FLOA)(?!.*NO.*NULL))':'real', '((REAL|DOUB|FLOA)(.*NO.*NULL))':'real_not_null', 
'((NUMERIC|JSON|GUID|UUID)(?!.*NO.*NULL))':'numeric', '((NUMERIC|JSON|GUID|UUID)(.*NO.*NULL))':'numeric_not_null'}

dict_types = {'zero':zero, 'integer':integer, 'integer_not_null':integer_not_null, 'boolean':boolean, 'boolean_not_null':boolean_not_null, 
'real':real, 'real_not_null':real_not_null, 'blob':blob, 'blob_not_null':blob_not_null, 'text':text, 'text_not_null':text_not_null,
'numeric':numeric, 'numeric_not_null':numeric_not_null}

dict_payload = {'zero':nothing, 'integer':numbers, 'integer_not_null':numbers_not_null, 'boolean':nothing, 'boolean_not_null':nothing,
'real':floating, 'real_not_null':floating_not_null, 'blob':everything, 'blob_not_null':everything_not_null, 'text':strings, 
'text_not_null':strings_not_null, 'numeric':everything, 'numeric_not_null':everything_not_null}



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



#Function that replaces types with regexes for each table, retrieved from config.py (e.g. 'INTEGER PRIMARY KEY' (necessarily a 0) --> 'zero' --> r'[\x00]{1}')
def regex_types(fields_types_):
    for key,value in types_sub.items():
        fields_types_ = re.sub(rf'.*{key}.*', value, fields_types_, flags=re.IGNORECASE)
    return fields_types_



#Function that builds regexes for each table, concatenating regexes of header of record + regexes of each column
def build_regex(header_pattern, headers_patterns, list_fields, lists_fields, regex_constructs, tables_regexes, starts_headers, scenario, freeblock=bool, type1=bool): #payloads_patterns
    
    headers_patterns_copy = []
    j=0
    #For each table
    for i in range(len(fields_numbers)):
        #If length of header smaller than number of columns of given table
        while len(header_pattern) < fields_numbers[i]:
            #Append type to header
            fields_types_ = fields_types[j]
            #Replace each type with regex of type : e.g. ['INTEGER NOT NULL', 'INTEGER NOT NULL', 'LONGVARCHAR NOT NULL'] --> #e.g. ['integer', 'integer', 'text']
            fields_types_ = regex_types(fields_types_)
            if fields_types_ not in types_list:
                fields_types_ = 'numeric'
            #Add it to list header_pattern to create a header pattern
            header_pattern.append(fields_types_)
            j+=1
        #List of header patterns
        headers_patterns.append(header_pattern)
        header_pattern_copy = header_pattern.copy()
        headers_patterns_copy.append(header_pattern_copy)
        # payload_pattern = header_pattern.copy()
        # payloads_patterns.append(payload_pattern)
        #Empty list to go to next table
        header_pattern = []


    k=0
    #For each table
    for i in range(len(fields_numbers)):
        #Same but for fields names
        while len(list_fields) < fields_numbers[i]:
            fields_names_ = fields_names[k]
            list_fields.append(fields_names_)
            k+=1
        lists_fields.append(list_fields)
        #Empty list to go to next table
        list_fields = []


    #Generation of regexes for payload_length, serial types array length, freeblock length
    payload_min_max = []
    freeblock_min_max = []
    
    fb_min = 4
    fb_max = 4

    count_min = 1
    count_max = 2

    #Next freeblock offset on 2-bytes
    next_freeblock = r'([\x00-\xff]{2})'
    
    array_min_max = []
    counter_min = 1
    counter_max = 1

    #Types that have a fixed min/max size in bytes VS that size can vary
    multiple_bytes = ['text', 'text_not_null', 'numeric' 'numeric_not_null' 'blob' 'blob_not_null']
    fixed_bytes = ['zero', 'boolean', 'boolean_not_null', 'integer', 'integer_not_null', 'real', 'real_not_null']


    for header_pattern in headers_patterns:
        
        #If types for a given table are all of a fixed min/max size
        if set(header_pattern).issubset(fixed_bytes):
            a = header_pattern.count('zero')
            b = header_pattern.count('boolean')
            c = header_pattern.count('boolean_not_null')
            d = header_pattern.count('integer')
            e = header_pattern.count('integer_not_null')
            f = header_pattern.count('real')
            g = header_pattern.count('real_not_null')
            
            #E.g. an integer has min = 1 byte, max = 9 bytes
            minimum = (a*1 + b*1 + c*1 + d*1 + e*2 + f*1 + g*9)
            maximum = (a*1 + b*1 + c*1 + d*10 + e*10 + f*9 + g*9)
    
            #Freeblock length is on 2-bytes
            if freeblock:
                fb_min += minimum
                fb_max += maximum

                if fb_min < 16:
                    fb_min = format(fb_min,'x').zfill(2)
                else:
                    fb_min = format(fb_min,'x')
                if fb_max < 16:
                    fb_max = format(fb_max,'x').zfill(2)
                else:
                    fb_max = format(fb_max,'x')

                #Regex for freeblock length, min and max size
                freeblock_length = rf'([\x00]{{1}}[\x{fb_min}-\x{fb_max}]{{1}})'

                freeblock_min_max.append(freeblock_length)

                fb_min = 4
                fb_max = 4
            
            else:
                count_min += minimum
                count_max += maximum

                count_min = format(count_min,'x').zfill(2)
                count_max = format(count_max,'x').zfill(2)
                
                #Regex for payload length, min and max size
                payload_length = rf'([\x{count_min}-\x{count_max}]{{1}})'

                payload_min_max.append(payload_length)

                count_min = 1
                count_max = 2

        else:
            #If size in bytes is not fixed for types
            h = header_pattern.count('integer_not_null')
            i = header_pattern.count('real_not_null')
            j = header_pattern.count('text_not_null')
            k = header_pattern.count('numeric_not_null')
            l = header_pattern.count('blob_not_null')
            
            #We can still compute a min size, based on number of columns and types
            minimum = (len(header_pattern) + h + i + j + k + l)


            if freeblock:
                fb_min += minimum

                if fb_min < 16:
                    fb_min = format(fb_min,'x').zfill(2)
                else:
                    fb_min = format(fb_min,'x')

                freeblock_length = rf'([\x00-\xff]{{1}}[\x{fb_min}-\xff]{{1}})'

                freeblock_min_max.append(freeblock_length)
                
                fb_min = 4

            else:
                count_min += minimum
                count_min = format(count_min,'x').zfill(2)

                payload_length = rf'((([\x81-\xff]{{1,8}}[\x00-\x80]{{1}})|([\x{count_min}-\x80]{{1}})){{1}})'
                
                payload_min_max.append(payload_length)

                count_min = 1
        

        #Regex for serial types array length, min and max size
        if not freeblock or scenario == 3:
            for element in header_pattern:
                counter_min += 1
                if element in multiple_bytes:
                    counter_max += 9
                else:
                    counter_max += 1
            if counter_max > 128:
                x = round(counter_max/128)
                y = counter_max%128
                counter_min = format(counter_min,'x').zfill(2)
                counter_max = format(128,'x').zfill(2)
                x = 129
                x = format(x,'x').zfill(2)
                y = format(y,'x').zfill(2)
                serial_types_array_length = rf'(([\x{counter_min}-\x{counter_max}]{{1}})|([\x{x}]{{1}}[\x00-\x{y}]{{1}}))'
                array_min_max.append(serial_types_array_length)
            else:
                counter_min = format(counter_min,'x').zfill(2)
                counter_max = format(counter_max,'x').zfill(2)
                serial_types_array_length = rf'([\x{counter_min}-\x{counter_max}]{{1}})'
                array_min_max.append(serial_types_array_length)

            counter_min = 1
            counter_max = 1

        #If type1 overwritten, remove first type from types and surround header group by ()
        if type1:
            header_pattern[0] = '('
            header_pattern.insert(len(header_pattern), ')')
        
        #Else, surround header group by ()
        else:
            header_pattern.insert(0, '(')
            header_pattern.insert(len(header_pattern), ')')

    
    #Regex for row_id
    row_id = r'((([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1})){1})'
 
    #Start of header if freeblock (offset of next freeblock + freeblock length)
    if freeblock:
        if scenario == 3:
            for index in range(len(freeblock_min_max)):
                start_header = '(' + next_freeblock + freeblock_min_max[index] + array_min_max[index] + ')'
                starts_headers.append(start_header)
        else:
            for index in range(len(freeblock_min_max)):
                start_header = '(' + next_freeblock + freeblock_min_max[index] + ')'
                starts_headers.append(start_header)
    
    #Start of header if no freeblock (payload length, row_id, serial types array length)
    else:
        for index in range(len(payload_min_max)):
            start_header = '(' + payload_min_max[index] + row_id + array_min_max[index] + ')'
            starts_headers.append(start_header)

    # for payload_pattern in payloads_patterns:
    #     for n,i in enumerate(payload_pattern):
    #         for k,v in dict_payload.items():
    #             if i == k:
    #                 payload_pattern[n] = v
    #     payload_pattern.insert(0, '(')
    #     payload_pattern.insert(len(payload_pattern), ')')


    #If we know that payload of record contains a certain word
    # payloads_patterns = r'(?<=.*\x68\x74\x74\x70.*)' #http
    # for i in range(len(headers_patterns)):
    #     headers_patterns[i].extend(payloads_patterns)


    #For each header pattern, add start of header [payload length, rowid and types length] (or freeblock) before list of types --> [payload length, rowid, types length, type1, type2, etc.]
    for header_pattern in headers_patterns:

        #Replace each literal expression of regex with real regex
        for n,i in enumerate(header_pattern):
            for k,v in dict_types.items():
                if i == k:
                    header_pattern[n] = v

        index = headers_patterns.index(header_pattern)
        header_pattern.insert(0, starts_headers[index])
        
        
        #Concatenate all regexes of a table
        #E.g. [[\x00]{1}, [\x00-\x09]{1}, [\x00-\x09]{1}] --> [[\x00]{1}[\x00-\x09]{1}[\x00-\x09]{1}]
        regex_construct = ''.join(header_pattern)
        #Transform the whole regex in bytes b'' so that we can search regex in file afterwards
        regex_construct = regex_construct.encode('UTF8')
        #Compile regex to be usable
        regex_construct = re.compile(regex_construct)
        #Append to list of regexes
        regex_constructs.append(regex_construct)


    #Link together table name, table's fields and regex for that table
    for i in range(len(regex_constructs)):
        table_regex = {tables_names[i]:[lists_fields[i], headers_patterns_copy[i], regex_constructs[i]]}
        tables_regexes.append(table_regex)

    return tables_regexes





#Function that decodes bytes from possible header into integers (so that we can do calculations on it after) and appends them to unknown_header list
def decode_unknown_header(unknown_header, unknown_header_2, a, b, limit, len_start_header, scenario, freeblock=bool):
    #WITH ROWID
    count = 0
    #While not end of the match
    while count <= (b-a-1):
        #If [payload length, rowid, types length] part --> not serial types so just append(byte) and not append(serialTypes(byte))
        if len(unknown_header) < len_start_header:
            #If it's a freeblock, read 2 bytes then 2 bytes
            if freeblock and scenario==3:
                byte = int(struct.unpack('>H', file.read(2))[0])
                unknown_header.append(byte)
                unknown_header_2.append(byte)
                count+=2
                byte1 = int(struct.unpack('>H', file.read(2))[0])
                unknown_header.append(byte1)
                unknown_header_2.append(byte1)
                count+=2
                byte2 = int(struct.unpack('>B', file.read(1))[0])
                unknown_header.append(byte2)
                unknown_header_2.append(byte2)
                count+=1
            
            elif freeblock and scenario!=3:
                byte = int(struct.unpack('>H', file.read(2))[0])
                unknown_header.append(byte)
                unknown_header_2.append(byte)
                count+=2
            
            else:
                #Read byte by byte, convert in int, and append to unknown_header list
                byte = int(struct.unpack('>B', file.read(1))[0])
                if byte < 128:
                    unknown_header.append(byte)
                    unknown_header_2.append(byte)
                    count+=1
                #Deal with Huffman coding until 9 successive bytes > 0x80 or > 128
                else:
                    cont1 = int(struct.unpack('>B', file.read(1))[0])
                    byte1 = int(huffmanEncoding(byte, cont1),16)
                    if cont1 < 128:
                        unknown_header.append(byte1)
                        unknown_header_2.append(byte1)
                        count+=2
                    else:
                        cont2 = int(struct.unpack('>B', file.read(1))[0])
                        byte2 = int(huffmanEncoding(byte1, cont2),16)
                        count+=2
                        if cont2 < 128:
                            unknown_header.append(byte2)
                            unknown_header_2.append(byte2)
                            count+=1
                        else:
                            count+=1
                            cont3 = int(struct.unpack('>B', file.read(1))[0])
                            byte3 = int(huffmanEncoding(byte2, cont3),16)
                            if cont3 < 128:
                                unknown_header.append(byte3)
                                unknown_header_2.append(byte3)
                                count+=1
                            else:
                                count+=1
                                cont4 = int(struct.unpack('>B', file.read(1))[0])
                                byte4 = int(huffmanEncoding(byte3, cont4),16)
                                if cont4 < 128:
                                    unknown_header.append(byte4)
                                    unknown_header_2.append(byte4)
                                    count+=1
                                else:
                                    count+=1
                                    cont5 = int(struct.unpack('>B', file.read(1))[0])
                                    byte5 = int(huffmanEncoding(byte4, cont5),16)
                                    if cont5 < 128:
                                        unknown_header.append(byte5)
                                        unknown_header_2.append(byte5)
                                        count+=1
                                    else:
                                        count+=1
                                        cont6 = int(struct.unpack('>B', file.read(1))[0])
                                        byte6 = int(huffmanEncoding(byte5, cont6),16)
                                        if cont6 < 128:
                                            unknown_header.append(byte6)
                                            unknown_header_2.append(byte6)
                                            count+=1
                                        else:
                                            count+=1
                                            cont7 = int(struct.unpack('>B', file.read(1))[0])
                                            byte7 = int(huffmanEncoding(byte6, cont7),16)
                                            if cont7 < 128:
                                                unknown_header.append(byte7)
                                                unknown_header_2.append(byte7)
                                                count+=1
                                            else:
                                                count+=1
                                                cont8 = int(struct.unpack('>B', file.read(1))[0])
                                                byte8 = int(huffmanEncoding(byte7, cont8),16)
                                                if cont8 < 128:
                                                    unknown_header.append(byte8)
                                                    unknown_header_2.append(byte8)
                                                    count+=1
                                                else:
                                                    count+=1
                                                    cont9 = int(struct.unpack('>B', file.read(1))[0])
                                                    byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                    unknown_header.append(byte9)
                                                    unknown_header_2.append(byte9)
        
        #If [types] part --> type1, type2, etc. --> append(serialTypes(byte))
        else:
            #list limit to know how many bytes takes start of header (because 3 integers not necessarily only 3 bytes)
            limit.append(count)
            byte = int(struct.unpack('>B', file.read(1))[0])
            if byte < 128:
                unknown_header.append(serialTypes(byte))
                unknown_header_2.append(byte)
                count+=1
            #Deal with Huffman coding until 9 successive bytes > 0x80 or > 128
            else:
                cont1 = int(struct.unpack('>B', file.read(1))[0])
                byte1 = int(huffmanEncoding(byte, cont1),16)
                if cont1 < 128:
                    unknown_header.append(serialTypes(byte1))
                    unknown_header_2.append(byte1)
                    count+=2
                else:
                    cont2 = int(struct.unpack('>B', file.read(1))[0])
                    byte2 = int(huffmanEncoding(byte1, cont2),16)
                    count+=2
                    if cont2 < 128:
                        unknown_header.append(serialTypes(byte2))
                        unknown_header_2.append(byte2)
                        count+=1
                    else:
                        count+=1
                        cont3 = int(struct.unpack('>B', file.read(1))[0])
                        byte3 = int(huffmanEncoding(byte2, cont3),16)
                        if cont3 < 128:
                            unknown_header.append(serialTypes(byte3))
                            unknown_header_2.append(byte3)
                            count+=1
                        else:
                            count+=1
                            cont4 = int(struct.unpack('>B', file.read(1))[0])
                            byte4 = int(huffmanEncoding(byte3, cont4),16)
                            if cont4 < 128:
                                unknown_header.append(serialTypes(byte4))
                                unknown_header_2.append(byte4)
                                count+=1
                            else:
                                count+=1
                                cont5 = int(struct.unpack('>B', file.read(1))[0])
                                byte5 = int(huffmanEncoding(byte4, cont5),16)
                                if cont5 < 128:
                                    unknown_header.append(serialTypes(byte5))
                                    unknown_header_2.append(byte5)
                                    count+=1
                                else:
                                    count+=1
                                    cont6 = int(struct.unpack('>B', file.read(1))[0])
                                    byte6 = int(huffmanEncoding(byte5, cont6),16)
                                    if cont6 < 128:
                                        unknown_header.append(serialTypes(byte6))
                                        unknown_header_2.append(byte6)
                                        count+=1
                                    else:
                                        count+=1
                                        cont7 = int(struct.unpack('>B', file.read(1))[0])
                                        byte7 = int(huffmanEncoding(byte6, cont7),16)
                                        if cont7 < 128:
                                            unknown_header.append(serialTypes(byte7))
                                            unknown_header_2.append(byte7)
                                            count+=1
                                        else:
                                            count+=1
                                            cont8 = int(struct.unpack('>B', file.read(1))[0])
                                            byte8 = int(huffmanEncoding(byte7, cont8),16)
                                            if cont8 < 128:
                                                unknown_header.append(serialTypes(byte8))
                                                unknown_header_2.append(byte8)
                                                count+=1
                                            else:
                                                count+=1
                                                cont9 = int(struct.unpack('>B', file.read(1))[0])
                                                byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                unknown_header.append(serialTypes(byte9))
                                                unknown_header_2.append(byte9)

    #Return possible headers without filtering on payload length = sum of types, return limit to know number of start header bytes
    return unknown_header, unknown_header_2, limit




def decode_record(table, b, payload, unknown_header, unknown_header_2, fields_regex, record_infos, z):
    #Go to the end of the match to start reading payload content that comes just after header
    file.seek(b)
    #For each length of each type
    for l in ((unknown_header)[z:]):
        
        #Read bytes for that length and decode it according to encoding : e.g. [48, 42, 8, 0, 24, 7, 1, 0, 8, 0] --> read following number of bytes [0, 24, 7, 1, 0, 8, 0]
        payload_field = file.read(l)
        #Append to payload content list : e.g. [0, 24, 7, 1, 0, 8, 0] --> ['', 'https://www.youtube.com/', 'YouTube', 3, '', 13263172804027223, '']
        payload.append(payload_field)

    for n,i in enumerate(fields_regex[1]):
        if i == 'zero':
            try:
                payload[n] = unknown_header[1]
            except IndexError:
                pass
        elif i == 'boolean' or i == 'boolean_not_null' or i == 'integer' or i == 'integer_not_null':
            payload[n] = int.from_bytes(payload[n], byteorder='big', signed=True)
            try:
                if unknown_header_2[z+n] == 8:
                    payload[n] = 0
                elif unknown_header_2[z+n] == 9:
                    payload[n] = 1
            except IndexError:
                pass
        else:
            try:
                payload[n] = payload[n].decode('utf-8', errors='ignore')
                payload[n] = payload[n].replace("'", " ")
            except IndexError:
                pass


    if (len(unknown_header) > 3) and (unknown_header[3] == 0):
        payload[0] = unknown_header[1]

    payload.insert(0, record_infos)

    for element in payload:
        if isinstance(element, bytes):
            index = payload.index(element)
            payload.remove(element)
            payload.insert(index, 'error')

    connection = sqlite3.connect(output_db)
    cursor = connection.cursor()
    statement = "INSERT INTO" + " " + table + str(tuple(fields_regex[0])) + " VALUES " + str(tuple(payload))
    cursor.execute(statement)
    connection.commit()
    connection.close()



parser = argparse.ArgumentParser()
parser.add_argument('config')
parser.add_argument('main_file')
args = parser.parse_args()

#Open config file containing db infos, each table and type of column per table
with open(args.config, 'r') as config_file:
    #Load content
    data = json.load(config_file)
    #Close file
    config_file.close()

fields_numbers = []
fields_types = []
tables_names = []
fields_names = []

for key,value in data[0].items():
    if key == "output db":
        output_db = value

#TODO: read db_infos to retrieve db encoding (e.g. UTF-8)

#Because data[0] is general db information (db size, etc.)
#For each table:
for element in data[1:]:
    for key, value in element.items():
        tables_names.append(key)
        #Number of columns
        fields_number = len(value)
        #List of number of columns
        #e.g. for history.db from chrome: number of columns per table = [26, 4, 2, 9, 2, 7, 2, 2, 4, 3, 4, 3]
        fields_numbers.append(fields_number)
        #List of types per table
        for key1, value1 in value.items():
            field_type = value1
            field_name = key1
            fields_names.append(field_name)
            fields_types.append(field_type)



#Build regexes for each scenario (non-deleted records VS deleted records according to the parts the freeblock overwrites

header_pattern = []
headers_patterns = []
regex_constructs = []
tables_regexes = []
list_fields = []
lists_fields = []
starts_headers = []


build_regex(header_pattern, headers_patterns, list_fields, lists_fields, regex_constructs, tables_regexes, starts_headers, scenario=0, freeblock=False, type1=False) #payloads_patterns



header_pattern_s1 = []
headers_patterns_s1 = []
regex_constructs_s1 = []
tables_regexes_s1 = []
list_fields_s1 = []
lists_fields_s1 = []
starts_headers_s1 = []

build_regex(header_pattern_s1, headers_patterns_s1, list_fields_s1, lists_fields_s1, regex_constructs_s1, tables_regexes_s1, starts_headers_s1, scenario=1, freeblock=True, type1=True)


header_pattern_s2 = []
headers_patterns_s2 = []
regex_constructs_s2 = []
tables_regexes_s2 = []
list_fields_s2 = []
lists_fields_s2 = []
starts_headers_s2 = []

build_regex(header_pattern_s2, headers_patterns_s2, list_fields_s2, lists_fields_s2, regex_constructs_s2, tables_regexes_s2, starts_headers_s2, scenario=2, freeblock=True, type1=False)


header_pattern_s3 = []
headers_patterns_s3 = []
regex_constructs_s3 = []
tables_regexes_s3 = []
list_fields_s3 = []
lists_fields_s3 = []
starts_headers_s3 = []

build_regex(header_pattern_s3, headers_patterns_s3, list_fields_s3, lists_fields_s3, regex_constructs_s3, tables_regexes_s3, starts_headers_s3, scenario=3, freeblock=True, type1=False)




#Open db file (or other file) in binary format for reading
with open(args.main_file, 'r+b') as file:
    #mmap: instead of file.read() or file.readlines(), also works for big files, file content is internally loaded from disk as needed
    mm = mmap.mmap(file.fileno(), 0)




    """SCENARIO 0 : non-deleted records in db file (or records in journal/WAL files that keep same structure)"""
    # For each regex of types per table : e.g. table urls regex.Regex(b'(([\x01-\x80]{1})|([\x81-\xff]{1}[\x00-\x80]{1}))(([\x81-\xff]{1}[\x00-\x80]{1})|([\x00-\x80]{0,1}))(([\x81-\xff]{1}[\x00-\x80]{1})|([\x00-\x80]{1}))[\x00]{1}[\x00-\x09]{1}[\x00-\x09]{1}[\x00-\x09]{1}[\x00-\x09]{1}[\x00-\x09]{1}[\x00-\x09]{1}(([\x08]|[\x09]){1})(([\x08]|[\x09]){1})', flags=regex.A | regex.V0)
    for table_regex in tables_regexes:
        for table, fields_regex in table_regex.items():
            fields_regex[0].insert(0, 'record_infos')
            # Iterate over the file (mm) and search for a match
            # Update regex module : regex 2021.4.4 : overlapped=True finds overlapping matches (match starting at an offset inside another match)
            for match in re.finditer(fields_regex[2], mm, overlapped=True):
                unknown_header = []
                unknown_header_2 = []
                limit = []
                a = match.start()
                b = match.end()

                #Go to start of the match
                file.seek(a)

                #Decode unknown header bytes-->integers
                decode_unknown_header(unknown_header, unknown_header_2, a, b, limit, len_start_header=3, scenario=0, freeblock=False)

                #If limit is an empty list, header only contains start of header and is therefore a non-valid header
                if not limit:
                    pass
                #Else: may be a valid header
                else:
                    payload = []
                    #Filter: if payload length = sum of types in serial types array AND types not all = 0 AND serial types length = types length
                    if ((unknown_header[0] == somme(unknown_header[2:]))) and (somme(unknown_header[3:]) != 0) and (b-a-limit[0]+1 == unknown_header[2]):
                        record_infos = 'scenario 0, offset: ' + str(a)
                        decode_record(table, b, payload, unknown_header, unknown_header_2, fields_regex, record_infos, z=3)
                        
                        print('SCENARIO 0 :', table, unknown_header, payload, '\n\n')





    """SCENARIO 1 : overwritten : payload length, rowid, serial types array length, type 1 --> start at type 2"""
    #As for scenario 0
    for table_regex_s1 in tables_regexes_s1:
        for table_s1, fields_regex_s1 in table_regex_s1.items():
            fields_regex_s1[0].insert(0, 'record_infos')
            for match_s1 in re.finditer(fields_regex_s1[2], mm, overlapped=True):
                unknown_header_s1 = []
                unknown_header_2_s1 = []
                limit_s1 = []
                a = match_s1.start()
                b = match_s1.end()
                file.seek(a)

                decode_unknown_header(unknown_header_s1, unknown_header_2_s1, a, b, limit_s1, len_start_header=2, scenario=1, freeblock=True)

                if not limit_s1:
                    pass
                else:
                    payload_s1 = []
                    #Then we have to assume what type1 is
                    #WARNING: more false positives because more options
                    #WARNING: more duplicates if 2 or more tables with same number of columns --> will try for each type1
                    #If type1 is an integer, then a number from 0-9 is missing on first position on the header
                    if (fields_regex_s1[1])[0] == 'integer' or (fields_regex_s1[1])[0] == 'integer_not_null':
                        if (((somme(unknown_header_s1[2:]) + (b-a)) <= unknown_header_s1[1] <= (somme(unknown_header_s1[2:]) + (b-a) + 9))): #and (len(unknown_header_s1) > 3) for less false positives, but we miss all 1 and 2 columns records
                            #x is the unknown integer
                            x = unknown_header_s1[1] - somme(unknown_header_s1[2:]) - (b-a)
                            #Insert it on third place on header because it's type1 after freeblock
                            unknown_header_s1.insert(2, x)

                            record_infos = 'scenario 1, offset: ' + str(a)
                            decode_record(table_s1, b, payload_s1, unknown_header_s1, unknown_header_2_s1, fields_regex_s1, record_infos, z=2)
                            print('SCENARIO 1 :', table_s1, unknown_header_s1, payload_s1, '\n\n')


                    elif (fields_regex_s1[1])[0] == 'zero':
                        if ((somme(unknown_header_s1[2:]) + (b-a)) == ((unknown_header_s1[1])-1)):
                            #x is the unknown integer
                            x = 0
                            #Insert it on third place on header because it's type1 after freeblock
                            unknown_header_s1.insert(2, x)   

                            record_infos = 'scenario 1, offset: ' + str(a)
                            decode_record(table_s1, b, payload_s1, unknown_header_s1, unknown_header_2_s1, fields_regex_s1, record_infos, z=2)
                            print('SCENARIO 1 :', table_s1, unknown_header_s1, payload_s1, '\n\n')
                            




    """SCENARIO 2 : overwritten : payload length, rowid, serial types array length --> start at type 1"""
    #As for scenario 0
    for table_regex_s2 in tables_regexes_s2:
        for table_s2, fields_regex_s2 in table_regex_s2.items():
            fields_regex_s2[0].insert(0, 'record_infos')
            for match_s2 in re.finditer(fields_regex_s2[2], mm, overlapped=True):
                
                unknown_header_s2 = []
                unknown_header_2_s2 = []
                limit_s2 = []
                a = match_s2.start()
                b = match_s2.end()
                file.seek(a)

                decode_unknown_header(unknown_header_s2, unknown_header_2_s2, a, b, limit_s2, len_start_header=2, scenario=2, freeblock=True)
                
                if not limit_s2:
                    pass
                else:
                    payload_s2 = []
                    #WARNING: false positives with 1 and 2-columns headers that can easily match
                    #If sum of type + bytes of match = length of freeblock AND sum of types not equal to 0
                    if (((somme(unknown_header_s2[2:]) + (b-a)) == (unknown_header_s2[1])) and ((somme(unknown_header_s2[2:]) != 0))):

                        record_infos = 'scenario 2, offset: ' + str(a)
                        decode_record(table_s2, b, payload_s2, unknown_header_s2, unknown_header_2_s2, fields_regex_s2, record_infos, z=2)
                        print('SCENARIO 2: ', table_s2, unknown_header_s2, payload_s2, '\n\n')





    """SCENARIO 3 : overwritten : payload length, rowid --> start at serial types array length"""
    #As for scenario 0
    for table_regex_s3 in tables_regexes_s3:
        for table_s3, fields_regex_s3 in table_regex_s3.items():
            fields_regex_s3[0].insert(0, 'record_infos')
            for match_s3 in re.finditer(fields_regex_s3[2], mm, overlapped=True):
                
                unknown_header_s3 = []
                unknown_header_2_s3 = []
                limit_s3 = []
                a = match_s3.start()
                b = match_s3.end()
                file.seek(a)
                
                decode_unknown_header(unknown_header_s3, unknown_header_2_s3, a, b, limit_s3, len_start_header=3, scenario=3, freeblock=True)

                if not limit_s3:
                    pass
                else:
                    payload_s3 = []
                    #WARNING: false positives with 1 and 2-columns headers that can easily match
                    #If sum of type + bytes of match = length of freeblock AND sum of types not equal to 0
                    if (((somme(unknown_header_s3[2:]) + 4) == (unknown_header_s3[1])) and ((somme(unknown_header_s3[2:]) != 0)) and (b-a-limit_s3[0]+1 == unknown_header_s3[2])):
                        record_infos = 'scenario 3, offset: ' + str(a)
                        decode_record(table_s3, b, payload_s3, unknown_header_s3, unknown_header_2_s3, fields_regex_s3, record_infos, z=3)
                        print('SCENARIO 3: ', table_s3, unknown_header_s3, payload_s3, '\n\n')

#Close db file
file.close()
