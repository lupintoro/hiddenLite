#!/usr/bin/python3
import argparse, sys, os, struct, json, mmap, sqlite3, copy, tqdm
from typing import final
import regex as re
from ast import literal_eval





#Regexes for SQLite storage classes and data types
zero = r'([\x00]{1})'

integer = r'(([\x00-\x06]|[\x08-\x09]){1})'
integer_not_null = r'(([\x01-\x06]|[\x08-\x09]){1})'

boolean = r'(([\x00]|[\x08]|[\x09]){1})'
boolean_not_null = r'(([\x08]|[\x09]){1})'

real = r'(([\x00]|[\x07]){1})'
real_not_null = r'([\x07]{1})'

text = r'((([\x81-\xff]{1,3})([\x01|\x03|\x05|\x07|\x09|\x0b|\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}){1})|([\x00|\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}))'
text_not_null = r'((([\x81-\xff]{1,3})([\x01|\x03|\x05|\x07|\x09|\x0b|\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}){1})|([\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}))'

numeric_date = r'(([\x81-\xff]{1,3}[\x00-\x80]{1})|([\x00]{1})|([\x00-\x80]{1}))'
numeric_date_not_null = r'(([\x81-\xff]{1,3}[\x00-\x80]{1})|([\x00-\x80]{1}))'

numeric = r'(([\x81-\xff]{1,3}[\x00-\x80]{1})|([\x00]{1})|([\x00-\x80]{1}))'
numeric_not_null = r'(([\x81-\xff]{1,3}[\x00-\x80]{1})|([\x00-\x80]{1}))'

blob = r'((([\x81-\xff]{1,3})([\x00|\x02|\x04|\x06|\x08|\x0a|\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}){1})|([\x00|\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}))'
blob_not_null = r'((([\x81-\xff]{1,3})([\x00|\x02|\x04|\x06|\x08|\x0a|\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}){1})|([\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}))'



#Regexes for record payload content
#We just want to keep the record header, so we match the record payload implicitly by a lookahead assertion
#(?=...) Matches if ... matches next, but doesn’t consume any of the string. 
#This is called a lookahead assertion. For example, Isaac (?=Asimov) will match 'Isaac ' only if it’s followed by 'Asimov'.
nothing = r''
strings = r'([\x20-\xff]*)'
strings_not_null = r'([\x20-\xff]+)'
numbers = r'([\x00-\xff]{0,9})'
numbers_not_null = r'([\x00-\xff]{1,9})'
floating = r'((\'\')|([\x00-\xff]{8}))'
floating_not_null = r'([\x00-\xff]{8})'
everything = r'(^(?!.+\x00{10,}.+)([\x00-\xff]*))'
everything_not_null = r'(^(?!.+\x00{10,}.+)([\x00-\xff]+))'




#For every type of every column of every table in the config.json file, replace it with a generic identifying
types_sub = {'(INTEGER PRIMARY KEY)':'zero', '((INT)(?!.*NO.*NULL))':'integer', '((INT)(.*NO.*NULL))':'integer_not_null', 
'(BOOL(?!.*NO.*NULL))':'boolean', '(BOOL.*NO.*NULL)':'boolean_not_null', '((CHAR|TEXT|CLOB)(?!.*NO.*NULL))':'text', 
'((CHAR|TEXT|CLOB)(.*NO.*NULL))':'text_not_null', '(BLOB(?!.*NO.*NULL))':'blob', '(BLOB.*NO.*NULL)':'blob_not_null',
'((REAL|DOUB|FLOA)(?!.*NO.*NULL))':'real', '((REAL|DOUB|FLOA)(.*NO.*NULL))':'real_not_null',
'((NUMERIC|JSON|GUID|UUID)(?!.*NO.*NULL)(?!.*DATE))':'numeric', '((NUMERIC|JSON|GUID|UUID)(?!.*DATE)(.*NO.*NULL))':'numeric_not_null',
'((DATE)(?!.*NO.*NULL))':'numeric_date', '((DATE)(.*NO.*NULL))':'numeric_date_not_null'}

#After conversion of types, if there is an unknown type (not on this list) left, replace it with "numeric" or "numeric_not_null"
types_list = ('zero', 'integer', 'integer_not_null', 'boolean', 'boolean_not_null', 'real', 'real_not_null', 'text', 'text_not_null', 
'numeric', 'numeric_not_null', 'numeric_date', 'numeric_date_not_null' 'blob', 'blob_not_null')

#Replace each column type by its specific regex above
dict_types = {'zero':zero, 'integer':integer, 'integer_not_null':integer_not_null, 'boolean':boolean, 'boolean_not_null':boolean_not_null, 
'real':real, 'real_not_null':real_not_null, 'blob':blob, 'blob_not_null':blob_not_null, 'text':text, 'text_not_null':text_not_null,
'numeric_date':numeric_date, 'numeric_date_not_null':numeric_date_not_null, 'numeric':numeric, 'numeric_not_null':numeric_not_null}

#Replace each record payload by a specific regex per column type
dict_payload = {'zero':nothing, 'integer':numbers, 'integer_not_null':numbers_not_null, 'boolean':nothing, 'boolean_not_null':nothing,
'real':floating, 'real_not_null':floating_not_null, 'blob':everything, 'blob_not_null':everything_not_null, 'text':strings, 'text_not_null':strings_not_null, 
'numeric':everything, 'numeric_not_null':everything_not_null, 'numeric_date':everything, 'numeric_date_not_null':everything_not_null}

#Types that have a fixed min/max size in bytes VS types which size can vary
multiple_bytes = ('text', 'text_not_null', 'numeric_date', 'numeric_date_not_null' 'numeric' 'numeric_not_null' 'blob' 'blob_not_null')
fixed_bytes = ('zero', 'boolean', 'boolean_not_null', 'integer', 'integer_not_null', 'real', 'real_not_null')




#To decode Huffman coding
def huffmanEncoding(x,y):
    x = int(x)
    z = (x-128)*128
    a = z + int(y)
    
    return(hex(a))



#Function that translates SQLite serial types identifyings used in serial types array into their real value
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



#Function that replaces types with their specific regex for each table, retrieved from config.json (e.g. 'INTEGER PRIMARY KEY' (necessarily a 0) --> 'zero' --> r'[\x00]{1}')
def regex_types(fields_types_):
    for key,value in types_sub.items():
        fields_types_ = re.sub(rf'.*{key}.*', value, fields_types_, flags=re.IGNORECASE)
    
    return fields_types_




#Function that builds regexes for each table, concatenating regexes of header of record + regexes of each type of each column
def build_regex(header_pattern, headers_patterns, payloads_patterns, list_fields, lists_fields, regex_constructs, tables_regexes, starts_headers, scenario, freeblock=bool):
    
    headers_patterns_copy = []
    j=0
    #For each table
    for i in range(len(fields_numbers)):
        #While the length of the header is smaller than the number of columns of a given table
        while len(header_pattern) < fields_numbers[i]:
            #Append column type to header
            fields_types_ = fields_types[j]
            #Replace each type with its specific regex : e.g. ['INTEGER NOT NULL', 'INTEGER NOT NULL', 'LONGVARCHAR NOT NULL'] --> #e.g. ['integer', 'integer', 'text']
            fields_types_ = regex_types(fields_types_)
            #If it's an unknown type, replace it with "numeric" or "numeric_not_null"
            if fields_types_ not in types_list:
                if 'NOT NULL' in fields_types_:
                    fields_types_ = 'numeric_not_null'
                else:
                    fields_types_ = 'numeric'
            #Add each column type to the header_pattern list to create a header pattern per table
            header_pattern.append(fields_types_)
            j+=1
        #List of header patterns of all tables
        headers_patterns.append(header_pattern)
        header_pattern_copy = header_pattern.copy()
        headers_patterns_copy.append(header_pattern_copy)
        #Make a copy of the list to use it for the record payload regex search
        payload_pattern = copy.deepcopy(header_pattern)
        payloads_patterns.append(payload_pattern)
        #Empty list to move forward to the next table
        header_pattern = []


    k=0
    #For each table
    for i in range(len(fields_numbers)):
        #Do the same but for column names, to have a list of column names per table
        while len(list_fields) < fields_numbers[i]:
            fields_names_ = fields_names[k]
            list_fields.append(fields_names_)
            k+=1
        lists_fields.append(list_fields)
        list_fields = []


    #Generation of regexes for the beginning of the record header : payload_length, serial types array length, rowid OR next freeblock, freeblock length, etc.
    payload_min_max = []
    freeblock_min_max = []
    array_min_max = []
    fb_min, fb_max, count_min, count_max, counter_min, counter_max = 4, 4, 1, 2, 1, 1

    #General regex for the rowid on max 9-bytes (can be anything)
    row_id = r'((([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00-\x80]{1})){1})'
    
    #General regex for the next freeblock offset on 2-bytes (can be anything)
    next_freeblock = r'([\x00-\xff]{2})'
    
    
  
    #For each header pattern created before
    for header_pattern in headers_patterns:
        


        """REGEX FOR PAYLOAD/FREEBLOCK MIN/MAX LENGTHS"""
        
        #If the types of a given table are all of a fixed min/max size (e.g. only integers), count their occurrences
        if set(header_pattern).issubset(fixed_bytes):
            a = header_pattern.count('zero')
            b = header_pattern.count('boolean')
            c = header_pattern.count('boolean_not_null')
            d = header_pattern.count('integer')
            e = header_pattern.count('integer_not_null')
            f = header_pattern.count('real')
            g = header_pattern.count('real_not_null')
            
            #E.g. an integer has min = 1 byte, max = 9 bytes
            #Addition of all minimums and all maximums to have a range of lengths
            minimum = (a*1 + b*1 + c*1 + d*1 + e*2 + f*1 + g*9)
            maximum = (a*1 + b*1 + c*1 + d*10 + e*10 + f*9 + g*9)
    

            #If the record is overwritten by a freeblock
            #Freeblock length is on 2-bytes
            if freeblock:
                #We have a min/max freeblock length
                fb_min += minimum
                fb_max += maximum

                #If it's a "one-digit" hex number, fill it with a 0 (e.g. 9 --> 09)
                if fb_min < 16:
                    fb_min = format(fb_min,'x').zfill(2)
                else:
                    fb_min = format(fb_min,'x')
                if fb_max < 16:
                    fb_max = format(fb_max,'x').zfill(2)
                else:
                    fb_max = format(fb_max,'x')

                #Regex for the freeblock length, with different min and max size according to table
                freeblock_length = rf'([\x00]{{1}}[\x{fb_min}-\x{fb_max}]{{1}})'
                #Add the regex to a list of freeblock lengths regexes
                freeblock_min_max.append(freeblock_length)
                #Set min and max back to 4 (the minimum is 4 bytes because the freeblock itself is 4 bytes and the freeblock length counts itself)
                fb_min = 4
                fb_max = 4
            
            #If the record is not overwritten by a freeblock (intact)
            else:
                #We have a min/max payload length (first element of header)
                count_min += minimum
                count_max += maximum

                #Fill it to a "two-digits" hex number
                count_min = format(count_min,'x').zfill(2)
                count_max = format(count_max,'x').zfill(2)
                
                #Regex for the payload length, with different min and max size according to table
                payload_length = rf'([\x{count_min}-\x{count_max}]{{1}})'
                #Add the regex to a list of payload lengths regexes
                payload_min_max.append(payload_length)
                #Set min back to 1 and max back to 2(the minimum is 1 and the maximum is 2 bytes to count the 1-byte or the 2-bytes for the length of the serial types array)
                count_min = 1
                count_max = 2

        else:
            #If some types of a given table are not of a fixed min/max size (e.g. text), count their occurrences
            h = header_pattern.count('integer_not_null')
            i = header_pattern.count('real_not_null')
            j = header_pattern.count('text_not_null')
            k = header_pattern.count('numeric_not_null')
            l = header_pattern.count('blob_not_null')
            m = header_pattern.count('numeric_date_not_null')
            
            #We can still compute a min freeblock/payload length, based on the number of columns and types
            minimum = (len(header_pattern) + h + i + j + k + l + m)


            #If the record is overwritten by a freeblock
            if freeblock:
                #We have a min freeblock length
                fb_min += minimum
                
                #If it's a "one-digit" hex number, fill it with a 0 (e.g. 9 --> 09)
                if fb_min < 16:
                    fb_min = format(fb_min,'x').zfill(2)
                else:
                    fb_min = format(fb_min,'x')
                
                #Regex for the freeblock length, with different min size according to table
                #The maximum is 0xff, same for first byte, since freeblock is on 2-bytes --> min 00min, max ffff
                freeblock_length = rf'([\x00-\xff]{{1}}[\x{fb_min}-\xff]{{1}})'
                #Add the regex to a list of freeblock lengths regexes
                freeblock_min_max.append(freeblock_length)
                #Set min back to 4 (the minimum is 4 bytes because the freeblock itself is 4 bytes and the freeblock length counts itself)
                fb_min = 4

            #If the record is not overwritten by a freeblock (intact)
            else:
                #We have a min payload length (first element of header)
                count_min += minimum

                #Fill it to a "two-digits" hex number
                count_min = format(count_min,'x').zfill(2)
                
                #Regex for the payload length, with different min size according to table
                payload_length = rf'((([\x81-\xff]{{1,3}}[\x00-\x80]{{1}})|([\x{count_min}-\x80]{{1}})){{1}})'
                #Add the regex to a list of payload lengths regexes
                payload_min_max.append(payload_length)
                #Set min back to 1 (the minimum is 1 byte to count the 1-byte for the length of the serial types array)
                count_min = 1
        


        """REGEX FOR SERIAL TYPES ARRAY MIN/MAX LENGTH"""

        #If the record is not overwritten by a freeblock (intact) 
        #Or if it is but by scenarios 3, 4 & 5 (we still recover part or the entire byte of serial types array length)
        #In scenarios 1 & 2, this array length is completely overwritten
        if (not freeblock) or (scenario == 3 or 4 or 5):
            
            #We have a min serial types array length by additionning 1 to the minimum array length for each element (column type) of the header
            for element in header_pattern:
                counter_min += 1
                #If the column type is not of a fixed min/max size, addition 9 to the maximum array length
                if element in multiple_bytes:
                    counter_max += 9
                #If the column type is of a fixed min/max size, only addition 1 to the maximum array length
                else:
                    counter_max += 1
            
            #If the table has more than 128 columns (0x80, max on 1-byte, then Huffman encoding on 2-bytes)
            if counter_max > 128:
                #First byte : this only handles x81 x.. cases, so until 256 columns
                x = 129
                #Last byte maximum (last byte minimum is 00, e.g. x81 x00 = 129)
                y = counter_max%128
                
                #Fill it to a "two-digits" hex number
                counter_min = format(counter_min,'x').zfill(2)
                counter_max = format(128,'x').zfill(2)
                x = format(x,'x').zfill(2)
                y = format(y,'x').zfill(2)

                #Regex for the serial types array length, with different min/may sizes according to table
                serial_types_array_length = rf'(([\x{counter_min}-\x{counter_max}]{{1}})|([\x{x}]{{1}}[\x00-\x{y}]{{1}}))'
                #Add the regex to a list of array lengths regexes
                array_min_max.append(serial_types_array_length)
            
            #If the table has less than 128 columns
            else:
                #Fill it to a "two-digits" hex number
                counter_min = format(counter_min,'x').zfill(2)
                counter_max = format(counter_max,'x').zfill(2)
                
                #In scenario 4, half of the array length is overwritten --> the maximum for the eventual second byte is 80 
                if scenario == 4:
                    counter_max = 80
                #Regex for the serial types array length, with different min/max sizes according to table
                serial_types_array_length = rf'([\x{counter_min}-\x{counter_max}]{{1}})'
                #Add the regex to a list of array lengths regexes
                array_min_max.append(serial_types_array_length)
            
            #Set min and max back to 1 (we have at least one column per table to have possible records on it)
            counter_min = 1
            counter_max = 1


        #If type1 of the array is overwritten (scenario 1), remove first type from header pattern and surround header group by ()
        if scenario == 1:
            header_pattern[0] = '('
            header_pattern.insert(len(header_pattern), ')')
        
        #Else, surround header group by ()
        else:
            header_pattern.insert(0, '(')
            header_pattern.insert(len(header_pattern), ')')

    

 
    #Build a start of header according to each scenario and add it to a list of start headers
    #If the record is overwritten by a freeblock
    if freeblock:
        #Freeblock overwrites record until the rowid, so we recover from the serial types array length
        if scenario == 3:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['(', next_freeblock, freeblock_min_max[index], array_min_max[index], ')'])
                starts_headers.append(start_header)
        #Freeblock overwrites record until part of the serial types array length, so we recover part of it
        elif scenario == 4:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['(', next_freeblock, freeblock_min_max[index], array_min_max[index], ')'])
                starts_headers.append(start_header)
        #Freeblock overwrites record until part of the rowid, so we recover part of it
        elif scenario == 5:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['(', next_freeblock, freeblock_min_max[index], row_id, array_min_max[index], ')'])
                starts_headers.append(start_header)
        #Freeblock overwrites record until type1 or until array length, so we recover from type2 or type1
        elif scenario == 1 or scenario == 2:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['(', next_freeblock, freeblock_min_max[index], ')'])
                starts_headers.append(start_header)
    
    #If the record is not overwritten by a freeblock (intact)
    else:
        for index in range(len(payload_min_max)):
            start_header = "".join(['(', payload_min_max[index], row_id, array_min_max[index], ')'])
            starts_headers.append(start_header)

    


    #Concerning record payload
    for payload_pattern in payloads_patterns:
        
        #Optionnal command --keyword : if we want to search for records that contain a certain word (keyword searching)
        #If the user gives a keyword
        if args.keyword:
            #Transform this keyword in hexadecimal format \x..\x..
            hex_str = args.keyword.encode('utf-8')
            hex_str = hex_str.hex()
            hex_str = '\\x'.join(a+b for a,b in zip(hex_str[::2], hex_str[1::2]))
            hex_str = "".join(['\\x', str(hex_str)])
            hex_str = literal_eval(("'%s'"%hex_str))
            #Clear the existing payload pattern and replace it by the keyword
            payload_pattern.clear()
            payload_pattern.append(rf'.*{hex_str}.*')
        
        #If the user does not give a keyword
        else:
            #Replace each type identifying by a regex
            for n,i in enumerate(payload_pattern):
                for k,v in dict_payload.items():
                    if i == k:
                        payload_pattern[n] = v
        
        #Surround record payload pattern group by (?=( and )), ?= being for the lookahead assertion regex search
        #We just want to keep the record header, so we match the record payload implicitly by a lookahead assertion
        #(?=...) Matches if ... matches next, but doesn’t consume any of the string. 
        #This is called a lookahead assertion. For example, Isaac (?=Asimov) will match 'Isaac ' only if it’s followed by 'Asimov'.
        payload_pattern.insert(0, '(?=(')
        payload_pattern.insert(len(payload_pattern), '))')
    
    #Extend header pattern with payload pattern
    for i in range(len(headers_patterns)):
        headers_patterns[i].extend(payloads_patterns[i])



    #For each header pattern, add a start of header regex (payload length, rowid and types length OR freeblock and non-overwritten parts)
    for header_pattern in headers_patterns:

        #Replace each type identifying by a regex
        for n,i in enumerate(header_pattern):
            for k,v in dict_types.items():
                if i == k:
                    header_pattern[n] = v

        #Add start header at index 0 of header pattern
        index = headers_patterns.index(header_pattern)
        header_pattern.insert(0, starts_headers[index])
        
        
        #Concatenate all regexes of a given table
        #E.g. [[\x00]{1}, [\x00-\x09]{1}, [\x00-\x09]{1}] --> [[\x00]{1}[\x00-\x09]{1}[\x00-\x09]{1}]
        regex_construct = ''.join(header_pattern)
        #Transform the whole regex in bytes b'' so that we can search regex in file afterwards
        regex_construct = regex_construct.encode('UTF8')
        #Compile regex to be usable
        regex_construct = re.compile(regex_construct)
        #Append to list of regexes
        regex_constructs.append(regex_construct)



    #Link together table name, columns names, types identifyings and the whole regex for that table
    for i in range(len(regex_constructs)):
        table_regex = {tables_names[i]:[lists_fields[i], headers_patterns_copy[i], regex_constructs[i]]}
        
        #Add some information columns before the real table columns to specify the file from which the record is carved, its offset on the file and the scenario
        for table, fields_regex in table_regex.items():
            fields_regex[0].insert(0, 'carved_record_file')
            fields_regex[0].insert(0, 'carved_record_offset')
            fields_regex[0].insert(0, 'carving_scenario_number')

        tables_regexes.append(table_regex)


    return tables_regexes





#Function that decodes bytes from possible true header into integers (so that we can do calculations on it afterwards) and appends them to unknown_header list
def decode_unknown_header(unknown_header, unknown_header_2, a, b, limit, len_start_header, scenario, freeblock=bool):
    
    #a & b are the beginning and the end of the match respectivly
    
    count = 0
    
    #If the record is overwritten by a freeblock, read 2 bytes (next freeblock offset) then 2 bytes (length of this freeblock)
    if freeblock:
        byte = int(struct.unpack('>H', file.read(2))[0])
        unknown_header.append(byte)
        unknown_header_2.append(byte)
        count+=2
        
        byte = int(struct.unpack('>H', file.read(2))[0])
        unknown_header.append(byte)
        unknown_header_2.append(byte)
        count+=2


    #While not end of the match
    while count <= (b-a-1):
        #Before serial types part (start header length): append(byte) to unknown_header
        if len(unknown_header) < len_start_header:

            #Read byte by byte, convert in int, and append to unknown_header list
            byte = int(struct.unpack('>B', file.read(1))[0])
            if byte < 128:
                unknown_header.append(byte)
                unknown_header_2.append(byte)
                count+=1
            #Handle Huffman encoding until 9 successive bytes (> 0x80 or > 128)
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
                                                byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                unknown_header.append(byte9)
                                                unknown_header_2.append(byte9)
        
        
        #Serial types part : append(serialTypes(byte)) to unknown_header and not decoded bytes to unknown_header_2
        else:
            #Append limit to list to know how many bytes takes the start of the header (because 3 integers are not necessarily only 3 bytes)
            limit.append(count)
            #Read byte by byte, convert in int, and append to unknown_header list
            byte = int(struct.unpack('>B', file.read(1))[0])
            if byte < 128:
                unknown_header.append(serialTypes(byte))
                unknown_header_2.append(byte)
                count+=1
            #Handle Huffman encoding until 9 successive bytes (> 0x80 or > 128)
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
                                                byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                unknown_header.append(serialTypes(byte9))
                                                unknown_header_2.append(byte9)


    return unknown_header, unknown_header_2, limit




#Function that decodes the record payload based on the possible headers
def decode_record(b, payload, unknown_header, unknown_header_2, fields_regex, record_infos_0, record_infos_1, record_infos_2, z):
    
    #Go to the end of the match to start reading payload content that comes just after the header/match
    file.seek(b)
    
    #For each field's length of the record
    for l in ((unknown_header)[z:]):
        
        #Read bytes for that length and decode it according to encoding : 
        #e.g. possible header = [48, 42, 8, 0, 24, 7, 1, 0, 8, 0] 
        #--> read the following number of bytes from type1 [0, 24, 7, 1, 0, 8, 0]
        payload_field = file.read(l)
        
        #Append the content to payload list :
        #e.g. [0, 24, 7, 1, 0, 8, 0] --> ['', 'https://www.youtube.com/', 'YouTube', 3, '', 13263172804027223, '']
        payload.append(payload_field)

    #For each identifying type per column
    for n,i in enumerate(fields_regex[1]):
        
        #If type is zero (INTEGER PRIMARY KEY --> rowid)
        if i == 'zero':
            #Then we can retrieve the rowid from the header, in second place
            try:
                payload[n] = unknown_header[1]
            except IndexError:
                pass
        
        #If type is a boolean or integer or real
        elif i == 'boolean' or i == 'boolean_not_null' or i == 'integer' or i == 'integer_not_null' or i == 'real' or i == 'real_not_null':
            #Then convert bytes into integers
            try:
                payload[n] = int.from_bytes(payload[n], byteorder='big', signed=True)
            except IndexError:
                pass
            
            #If in unknown_header_2 not decoded there was an 8, then it's a 0 in the record
            #If there was a 9, then it's a 1 in the record
            try:
                if unknown_header_2[z+n] == 8:
                    payload[n] = 0
                elif unknown_header_2[z+n] == 9:
                    payload[n] = 1
            except IndexError:
                pass
        
        #If type contains 'DATE'
        elif i == 'numeric_date' or i == 'numeric_date_not_null':
            try:
                #Then try to convert it from a 4-byte integer (e.g. Julian day number expressed as an integer, unixepoch, ...)
                if unknown_header_2[z+n] == 4:
                    payload[n] = int.from_bytes(payload[n], byteorder='big', signed=False)
                #Else it's a string value, so decode it from utf-8 (e.g. YYYY-MM-DD HH:MM:SS.SSS)
                else:
                    try:
                        payload[n] = payload[n].decode('utf-8', errors='ignore')
                        #Sanitize SQL comments and single quotes
                        payload[n] = payload[n].replace("'", " ")
                        payload[n] = payload[n].replace("--", "  ")
                    except IndexError:
                        pass
            except IndexError:
                pass
        
       
        #Else, decode as a string from utf-8
        else:
            try:
                payload[n] = payload[n].decode('utf-8', errors='ignore')
                #Sanitize SQL comments and single quotes
                payload[n] = payload[n].replace("'", " ")
                payload[n] = payload[n].replace("--", "  ")
            except IndexError:
                pass


    #To retrieve the rowid for which the first column type is not an INTEGER PRIMARY KEY
    if (len(unknown_header) > 3) and (unknown_header[3] == 0):
        payload[0] = unknown_header[1]

    #Add information to information columns before the real table columns to specify the file from which the record is carved, its offset on the file and the scenario
    payload.insert(0, record_infos_2)
    payload.insert(0, record_infos_1)
    payload.insert(0, record_infos_0)

    #If some elements are still not decoded and therefore still in bytes, convert element in 'error'
    for element in payload:
        if isinstance(element, bytes):
            index = payload.index(element)
            payload.remove(element)
            payload.insert(index, 'error')





#Command-line arguments and options
parser = argparse.ArgumentParser()
parser.add_argument("--config", nargs='?', help='Provide a config.json file generated by config.py, containing the main db schema.')
parser.add_argument("--input", nargs='+', help='Provide all the files or a directory in which you want to search for records.')
parser.add_argument("--keyword", nargs='?', required=False, help='Retrieve only records containing a certain word, e.g. --keyword http')
parser.add_argument("--output", nargs='?', help='Where do you want to save the output database file?')
args = parser.parse_args()




#Retrieve file, files or directory given as input

#List of files
main_files = []
#List of files' paths
main_files_paths = []

#For each file provided as input
for mainfile in args.input:
    #If it's a directory
    if os.path.isdir(mainfile):
        #Look for files inside
        for parent, dirnames, filenames in os.walk(mainfile):
            #Search for (associated) files with same name as main database name (e.g. if mmssms.db, search for mmssms.db, mmssms.db-journal, mmssms.db-journal-slack, etc.)
            for fn in filenames:
                associated_file = args.config.replace('config_', '')
                associated_file = associated_file.replace('.json', '')
                #For each associated file, append their name to main_files list and path to main_files_paths list
                if associated_file in fn:
                    filepath = os.path.join(parent, fn)
                    main_files.append(fn)
                    main_files_paths.append(filepath)
    #If it's file(s)
    elif os.path.isfile(mainfile):
        #Append their name to main_files list
        main_files.append(mainfile)
    #Else, nor file nor directory
    else:
        print("Nor file(s) nor directory")




#List of CREATE statements to create output database
create_statements = []

#Open config.json file containing db infos, each table, column and type of column
with open(args.config, 'r') as config_file:
    #Load content
    data = json.load(config_file)

    #Close file
    config_file.close()

#Db general information is in data[0], all tables and columns/types are in data[1:]
for key,value in data[0].items():
    #Name the output database by retrieving the main database name in config.json db infos
    if key == "file name":
        output_db = "".join(['output_', value, '.db'])
    #Quit script if encoding other than utf-8
    if key == "text encoding" and value != 1:
        sys.exit("Database encoding is not utf-8!")

#Retrieve the database schema from data[1:]
for element in data[1:]:
    #To create an output database based on this schema and insert information columns before the real columns 
    for key,value in element.items():
        statement = json.dumps(value)
        statement = statement.replace('}', ')')
        statement = statement.replace('"', '')
        statement = statement.replace(':', '')
        #Replace all INTEGER PRIMARY KEY by INTEGER because they might not be unique : the output database has carved_record_id column as INTEGER PRIMARY KEY autoincrement
        statement = statement.replace('INTEGER PRIMARY KEY', 'INTEGER')
        statement = statement.replace('{', '(carved_record_id INTEGER PRIMARY KEY AUTOINCREMENT, carving_scenario_number TEXT, carved_record_offset INTEGER, carved_record_file TEXT, ')
        #Create tables with statements constructed
        create_statement = "".join(['CREATE TABLE ', key, ' ', statement])
        create_statements.append(create_statement)




#Retrieve information about tables and columns

#List of number of columns per table, of types per field, of tables' names & of fields' names
fields_numbers, fields_types, tables_names, fields_names = [], [], [], []

#For each table:
for element in data[1:]:
    #For table_name, fields
    for key, value in element.items():
        #Append all the table's names to tables_names list
        tables_names.append(key)
        #Number of columns per table
        fields_number = len(value)
        #Append number of columns per table to fields_numbers list
        fields_numbers.append(fields_number)
        #List of types per table : column name and type
        for key1, value1 in value.items():
            field_name = key1
            field_type = value1
            #Append column name and type to fields_names and fields_types
            fields_names.append(field_name)
            fields_types.append(field_type)





"""Build regexes for each scenario (non-deleted records VS deleted records according to the parts that the freeblock overwrites)"""

#Scenario 0
header_pattern, headers_patterns, payloads_patterns, regex_constructs, tables_regexes, list_fields, lists_fields, starts_headers = [], [], [], [], [], [], [], []
build_regex(header_pattern, headers_patterns, payloads_patterns, list_fields, lists_fields, regex_constructs, tables_regexes, starts_headers, scenario=0, freeblock=False)

#Scenario 1
header_pattern_s1, headers_patterns_s1, payloads_patterns_s1, regex_constructs_s1, tables_regexes_s1, list_fields_s1, lists_fields_s1, starts_headers_s1 = [], [], [], [], [], [], [], []
build_regex(header_pattern_s1, headers_patterns_s1, payloads_patterns_s1, list_fields_s1, lists_fields_s1, regex_constructs_s1, tables_regexes_s1, starts_headers_s1, scenario=1, freeblock=True)

#Scenario 2
header_pattern_s2, headers_patterns_s2, payloads_patterns_s2, regex_constructs_s2, tables_regexes_s2, list_fields_s2, lists_fields_s2, starts_headers_s2 = [], [], [], [], [], [], [], []
build_regex(header_pattern_s2, headers_patterns_s2, payloads_patterns_s2, list_fields_s2, lists_fields_s2, regex_constructs_s2, tables_regexes_s2, starts_headers_s2, scenario=2, freeblock=True)

#Scenario 3
header_pattern_s3, headers_patterns_s3, payloads_patterns_s3, regex_constructs_s3, tables_regexes_s3, list_fields_s3, lists_fields_s3, starts_headers_s3 = [], [], [], [], [], [], [], []
build_regex(header_pattern_s3, headers_patterns_s3, payloads_patterns_s3, list_fields_s3, lists_fields_s3, regex_constructs_s3, tables_regexes_s3, starts_headers_s3, scenario=3, freeblock=True)

#Scenario 4
header_pattern_s4, headers_patterns_s4, payloads_patterns_s4, regex_constructs_s4, tables_regexes_s4, list_fields_s4, lists_fields_s4, starts_headers_s4 = [], [], [], [], [], [], [], []
build_regex(header_pattern_s4, headers_patterns_s4, payloads_patterns_s4, list_fields_s4, lists_fields_s4, regex_constructs_s4, tables_regexes_s4, starts_headers_s4, scenario=4, freeblock=True)

#Scenario 5
header_pattern_s5, headers_patterns_s5, payloads_patterns_s5, regex_constructs_s5, tables_regexes_s5, list_fields_s5, lists_fields_s5, starts_headers_s5 = [], [], [], [], [], [], [], []
build_regex(header_pattern_s5, headers_patterns_s5, payloads_patterns_s5, list_fields_s5, lists_fields_s5, regex_constructs_s5, tables_regexes_s5, starts_headers_s5, scenario=5, freeblock=True)




#List of INSERT statements to insert records in output database
statements = []

#For each file provided as input
#tqdm for progress bar per file processment
for mainfile in tqdm.tqdm(main_files, total=len(main_files), position=0, leave=True):
    #If a directory is given as input
    if os.path.isdir(mainfile):
        #The index of file being processed is the same for its path on main_files_paths list
        index = main_files.index(mainfile)
        open_file = main_files_paths[index]
    else:
        #Else, no need for path
        open_file = mainfile
    
    
    #Open mainfile in binary format and reading mode
    with open(open_file, 'r+b') as file:
        #mmap: file is mapped in memory and its content is internally loaded from disk as needed
        #instead of file.read() or file.readlines(), improves performance speading up the reading of files
        mm = mmap.mmap(file.fileno(), 0)



        
        #Process mainfile for each scenario

        """SCENARIO 0 : non-deleted records in a db file (or records in journal/WAL/slack files that keep intact structure)"""
        #For each regex per table
        for table_regex in tables_regexes:
            for table, fields_regex in table_regex.items():
                
                #Iterate over the file (mm) and search for matches
                #Update regex module : regex 2021.4.4 : overlapped=True finds overlapping matches (match starting at an offset inside another match)
                matches = [match for match in re.finditer(fields_regex[2], mm, overlapped=True)]
                
                #Process each match
                for match in matches:
                    
                    unknown_header, unknown_header_2, limit, payload = [], [], [], []
                    a = match.start()
                    b = match.end()
                    record_infos_0 = 'Scenario 0 : non-deleted or non-overwritten (WAL/journal files) records'
                    record_infos_1 = str(a)
                    record_infos_2 = str(mainfile)

                    #Go to start of the match
                    file.seek(a)

                    #Decode unknown header : bytes --> integers
                    decode_unknown_header(unknown_header, unknown_header_2, a, b, limit, len_start_header=3, scenario=0, freeblock=False)

                    #If limit is an empty list, header only contains start of header and is therefore a non-valid header
                    if not limit:
                        pass
                    #Else: may be a valid header
                    else:
                        #Filter: if payload length = sum of types in serial types array AND types not all = 0 AND serial types length = types length AND unknown header length > 3 (> start header)
                        if ((unknown_header[0] == sum(unknown_header[2:]))) and (sum(unknown_header[3:]) != 0) and (b-a-limit[0]+1 == unknown_header[2]) and (len(unknown_header) > 3):
                            #Then it might be a record so decode it
                            decode_record(b, payload, unknown_header, unknown_header_2, fields_regex, record_infos_0, record_infos_1, record_infos_2, z=3)
                            #If record contains the same number of columns as the table it matched with, append its insert statement to statements list
                            if len(fields_regex[0]) == len(payload):
                                insert_statement = "".join(["INSERT INTO", " ", table, str(tuple(fields_regex[0])), " VALUES ", str(tuple(payload))])
                                statements.append(insert_statement)





        """SCENARIO 1 : overwritten : payload length, rowid, serial types array length, type 1 --> record starts at type 2"""
        for table_regex_s1 in tables_regexes_s1:
            for table_s1, fields_regex_s1 in table_regex_s1.items():
                matches_s1 = [match_s1 for match_s1 in re.finditer(fields_regex_s1[2], mm, overlapped=True)]
                for match_s1 in matches_s1:
                    
                    unknown_header_s1, unknown_header_2_s1, limit_s1, payload_s1 = [], [], [], []
                    a = match_s1.start()
                    b = match_s1.end()
                    record_infos_0 = 'Scenario 1 : deleted records overwritten until type 2'
                    record_infos_1 = str(a)
                    record_infos_2 = str(mainfile)
                    
                    file.seek(a)

                    decode_unknown_header(unknown_header_s1, unknown_header_2_s1, a, b, limit_s1, len_start_header=2, scenario=1, freeblock=True)

                    if not limit_s1:
                        pass
                    
                    else:
                        
                        #Then we have to assume what type1 is since it's overwritten
                        #WARNING: more false positives because more options
                        #WARNING: more duplicates if 2 or more tables with same number of columns --> will try for each possible type1
                        #WARNING: if table has only 1 column, the whole header is overwritten and the record won't be recovered
                        
                        #If type1 is an integer, then a number from 0-9 is missing on first position on the header (works for booleans and reals too)
                        if (fields_regex_s1[1])[0] == 'integer' or 'integer_not_null':
                            if (((sum(unknown_header_s1[2:]) + (b-a+1)) <= unknown_header_s1[1] <= (sum(unknown_header_s1[2:]) + (b-a+1) + 9))):
                                #x is the unknown integer
                                x = unknown_header_s1[1] - sum(unknown_header_s1[2:]) - (b-a)
                                #Insert it on third place of the header because type1 follows the freeblock in this scenario
                                unknown_header_s1.insert(2, x)

                                decode_record(b, payload_s1, unknown_header_s1, unknown_header_2_s1, fields_regex_s1, record_infos_0, record_infos_1, record_infos_2, z=2)
                                
                                if len(fields_regex_s1[0]) == len(payload_s1):
                                    insert_statement = "".join(["INSERT INTO", " ", table_s1, str(tuple(fields_regex_s1[0])), " VALUES ", str(tuple(payload_s1))])
                                    statements.append(insert_statement)


                        #If type1 is an integer primary key, then a 0 is missing on first position on the header
                        elif (fields_regex_s1[1])[0] == 'zero':
                            if ((sum(unknown_header_s1[2:]) + (b-a+1)) == (unknown_header_s1[1])):

                                x = 0
                                unknown_header_s1.insert(2, x)

                                decode_record(b, payload_s1, unknown_header_s1, unknown_header_2_s1, fields_regex_s1, record_infos_0, record_infos_1, record_infos_2, z=2)
                                
                                if len(fields_regex_s1[0]) == len(payload_s1):
                                    insert_statement = "".join(["INSERT INTO", " ", table_s1, str(tuple(fields_regex_s1[0])), " VALUES ", str(tuple(payload_s1))])
                                    statements.append(insert_statement)





        """SCENARIO 2 : overwritten : payload length, rowid, serial types array length --> record starts at type 1"""
        for table_regex_s2 in tables_regexes_s2:
            for table_s2, fields_regex_s2 in table_regex_s2.items():
                matches_s2 = [match_s2 for match_s2 in re.finditer(fields_regex_s2[2], mm, overlapped=True)]
                for match_s2 in matches_s2:
                    
                    unknown_header_s2, unknown_header_2_s2, limit_s2, payload_s2 = [], [], [], []
                    a = match_s2.start()
                    b = match_s2.end()
                    
                    file.seek(a)
                    
                    decode_unknown_header(unknown_header_s2, unknown_header_2_s2, a, b, limit_s2, len_start_header=2, scenario=2, freeblock=True)
                
                    if not limit_s2:
                        pass
                    else:
                        #WARNING: false positives with 1 and 2-columns headers that can easily match
                        #If sum of types + bytes of header == length of freeblock AND sum of types not equal to 0
                        if (((sum(unknown_header_s2[2:]) + (b-a+1)) == (unknown_header_s2[1])) and ((sum(unknown_header_s2[2:]) != 0))):

                            record_infos_0 = 'Scenario 2 : deleted records overwritten until type 1'
                            record_infos_1 = str(a)
                            record_infos_2 = str(mainfile)
                            decode_record(b, payload_s2, unknown_header_s2, unknown_header_2_s2, fields_regex_s2, record_infos_0, record_infos_1, record_infos_2, z=2)
                            
                            if len(fields_regex_s2[0]) == len(payload_s2):
                                insert_statement = "".join(["INSERT INTO", " ", table_s2, str(tuple(fields_regex_s2[0])), " VALUES ", str(tuple(payload_s2))])
                                statements.append(insert_statement)





        """SCENARIO 3 : overwritten : payload length, rowid --> record starts at serial types array length"""
        for table_regex_s3 in tables_regexes_s3:
            for table_s3, fields_regex_s3 in table_regex_s3.items():
                matches_s3 = [match_s3 for match_s3 in re.finditer(fields_regex_s3[2], mm, overlapped=True)]
                for match_s3 in matches_s3:
                    
                    unknown_header_s3, unknown_header_2_s3, limit_s3, payload_s3 = [], [], [], []
                    a = match_s3.start()
                    b = match_s3.end()
                    record_infos_0 = 'Scenario 3 : deleted records overwritten until serial types array length'
                    record_infos_1 = str(a)
                    record_infos_2 = str(mainfile)
                    
                    file.seek(a)
                    
                    decode_unknown_header(unknown_header_s3, unknown_header_2_s3, a, b, limit_s3, len_start_header=3, scenario=3, freeblock=True)

                    if not limit_s3:
                        pass
                    else:
                        #If
                        if (((sum(unknown_header_s3[2:]) + 4) == (unknown_header_s3[1])) and ((sum(unknown_header_s3[2:]) != 0)) and (b-a-limit_s3[0]+1 == unknown_header_s3[2]) and (len(unknown_header_s3) > 3)):
                            
                            decode_record(b, payload_s3, unknown_header_s3, unknown_header_2_s3, fields_regex_s3, record_infos_0, record_infos_1, record_infos_2, z=3)
                            
                            if len(fields_regex_s3[0]) == len(payload_s3):
                                insert_statement = "".join(["INSERT INTO", " ", table_s3, str(tuple(fields_regex_s3[0])), " VALUES ", str(tuple(payload_s3))])
                                statements.append(insert_statement)





        """SCENARIO 4 : overwritten : payload length, rowid, part of serial types array length --> record starts at part of serial types array length"""
        for table_regex_s4 in tables_regexes_s4:
            for table_s4, fields_regex_s4 in table_regex_s4.items():
                matches_s4 = [match_s4 for match_s4 in re.finditer(fields_regex_s4[2], mm, overlapped=True)]
                for match_s4 in matches_s4:
                    
                    unknown_header_s4, unknown_header_2_s4, limit_s4, payload_s4 = [], [], [], []
                    a = match_s4.start()
                    b = match_s4.end()
                    record_infos_0 = 'Scenario 4 : deleted records overwritten until part of serial types array length'
                    record_infos_1 = str(a)
                    record_infos_2 = str(mainfile)
                    file.seek(a)

                    decode_unknown_header(unknown_header_s4, unknown_header_2_s4, a, b, limit_s4, len_start_header=3, scenario=4, freeblock=True)

                    if not limit_s4:
                        pass
                    else:
                        #We assume serial types array length cannot be > 2 bytes, otherwise too much columns, so here 1 byte is overwritten, 1 not
                        #If second part of serial types array length is less than 128 and if sum of bytes of header and sum of types equal to freeblock length and if sum of types not equal to 0
                        if ((unknown_header_s4[2] < 128) and ((sum(unknown_header_s4[3:]) + (b-a+1)) == (unknown_header_s4[1])) and ((sum(unknown_header_s4[3:]) != 0)) and (len(unknown_header_s4) > 3)):
                      
                            decode_record(b, payload_s4, unknown_header_s4, unknown_header_2_s4, fields_regex_s4, record_infos_0, record_infos_1, record_infos_2, z=3)
                            
                            if len(fields_regex_s4[0]) == len(payload_s4):
                                insert_statement = "".join(["INSERT INTO", " ", table_s4, str(tuple(fields_regex_s4[0])), " VALUES ", str(tuple(payload_s4))])
                                statements.append(insert_statement)
            




        """SCENARIO 5 : overwritten : payload length, part of rowid --> record starts at part of rowid"""
        #This scenario also covers SCENARIO 6 if payload length is 4 bytes --> start at rowid
        #As rowid can be anything, starting at part of it or starting at the entire rowid does not change anything
        #If payload length is exactly 4 bytes or more in length, it is greater than 512MB, which is unlikely to happen

        for table_regex_s5 in tables_regexes_s5:
            for table_s5, fields_regex_s5 in table_regex_s5.items():
                matches_s5 = [match_s5 for match_s5 in re.finditer(fields_regex_s5[2], mm, overlapped=True)]
                for match_s5 in matches_s5:
                    
                    unknown_header_s5, unknown_header_2_s5, limit_s5, payload_s5 = [], [], [], []
                    a = match_s5.start()
                    b = match_s5.end()
                    record_infos_0 = 'Scenario 5 : deleted records overwritten until part of rowid'
                    record_infos_1 = str(a)
                    record_infos_2 = str(mainfile)

                    file.seek(a)
                    
                    decode_unknown_header(unknown_header_s5, unknown_header_2_s5, a, b, limit_s5, len_start_header=4, scenario=5, freeblock=True)

                    if not limit_s5:
                        pass
                    else:
                        #If sum of type + bytes of match = length of freeblock AND sum of types not equal to 0
                        if (((sum(unknown_header_s5[4:]) + unknown_header_s5[3] + 4 + (b-a+1-4-unknown_header_s5[3])) == (unknown_header_s5[1])) and ((sum(unknown_header_s5[2:]) != 0)) and (len(unknown_header_s5) > 4)):
                    
                            decode_record(b, payload_s5, unknown_header_s5, unknown_header_2_s5, fields_regex_s5, record_infos_0, record_infos_1, record_infos_2, z=3)
                            
                            if len(fields_regex_s5[0]) == len(payload_s5):
                                insert_statement = "".join(["INSERT INTO", " ", table_s5, str(tuple(fields_regex_s5[0])), " VALUES ", str(tuple(payload_s5))])
                                statements.append(insert_statement)

        #Free the memory
        mm.close()

#Close mainfile
file.close()




#Connection to output database
connection = sqlite3.connect(args.output + output_db, isolation_level=None)

#Performance improvements
connection.execute('PRAGMA journal_mode=OFF')
connection.execute('PRAGMA locking_mode=EXCLUSIVE')
connection.execute("PRAGMA synchronous=OFF")
connection.execute("BEGIN TRANSACTION")


#CREATE tables
for create_statement in create_statements:

    #For columns' names sanitized with [], it must be removed to insert
    create_statement = create_statement.replace('[', '')
    create_statement = create_statement.replace(']', '')
    
    try:
        connection.execute(create_statement)
    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        print('sqlite error: ', e)


#INSERT records
for final_statement in statements:

    #For columns' names sanitized with [], it must be removed to insert
    final_statement = final_statement.replace('[', '')
    final_statement = final_statement.replace(']', '')
    
    #If a keyword is provided as optionnal argument
    if args.keyword:
        #Make sure it is really present in the record (lookahead assertion sometimes matches the word after the end of the record)
        if args.keyword in final_statement:
            try:
                connection.execute(final_statement)
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                print('sqlite error: ', e)
        else:
            pass
    #Else, insert all records
    else:
        try:
            connection.execute(final_statement)
        except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
            print('sqlite error: ', e)


#Commit transactions and close connection to output database
connection.commit()
connection.close()
