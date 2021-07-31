#!/usr/bin/python3
import argparse, sys, os, struct, json, mmap, sqlite3, tqdm, copy, time, multiprocessing
import regex as re
from ast import literal_eval
from itertools import chain
from multiprocessing import cpu_count




#Compute time elapsed after each scenario processing
start_time = time.time()




#Regexes for SQLite storage classes and data types
zero = r'([\x00]{1})'

integer = r'(([\x00-\x06]|[\x08-\x09]){1})'
integer_not_null = r'(([\x01-\x06]|[\x08-\x09]){1})'

boolean = r'(([\x00]|[\x08]|[\x09]){1})'
boolean_not_null = r'(([\x08]|[\x09]){1})'

real = r'([\x00-\x09]{1})'
real_not_null = r'([\x00-\x09]{1})'

#Strings : odd values
text = r'((([\x81-\xff]{1,8})([\x01|\x03|\x05|\x07|\x09|\x0b|\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}){1})|([\x00|\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}))'
text_not_null = r'((([\x81-\xff]{1,8})([\x01|\x03|\x05|\x07|\x09|\x0b|\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}){1})|([\x0d|\x0f|\x11|\x13|\x15|\x17|\x19|\x1b|\x1d|\x1f|\x21|\x23|\x25|\x27|\x29|\x2b|\x2d|\x2f|\x31|\x33|\x35|\x37|\x39|\x3b|\x3d|\x3f|\x41|\x43|\x45|\x47|\x49|\x4b|\x4d|\x4f|\x51|\x53|\x55|\x57|\x59|\x5b|\x5d|\x5f|\x61|\x63|\x65|\x67|\x69|\x6b|\x6d|\x6f|\x71|\x73|\x75|\x77|\x79|\x7b|\x7d|\x7f]{1}))'

#Blobs : odd values
blob = r'((([\x81-\xff]{1,8})([\x00|\x02|\x04|\x06|\x08|\x0a|\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}){1})|([\x00|\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}))'
blob_not_null = r'((([\x81-\xff]{1,8})([\x00|\x02|\x04|\x06|\x08|\x0a|\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}){1})|([\x0c|\x0e|\x10|\x12|\x14|\x16|\x18|\x1a|\x1c|\x1e|\x20|\x22|\x24|\x26|\x28|\x2a|\x2c|\x2e|\x30|\x32|\x34|\x36|\x38|\x3a|\x3c|\x3e|\x40|\x42|\x44|\x46|\x48|\x4a|\x4c|\x4e|\x50|\x52|\x54|\x56|\x58|\x5a|\x5c|\x5e|\x60|\x62|\x64|\x66|\x68|\x6a|\x6c|\x6e|\x70|\x72|\x74|\x76|\x78|\x7a|\x7c|\x7e|\x80]{1}))'

numeric_date = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00]{1})|([\x00-\x80]{1}))'
numeric_date_not_null = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x01-\x80]{1}))'

numeric = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x00]{1})|([\x00-\x80]{1}))'
numeric_not_null = r'(([\x81-\xff]{1,8}[\x00-\x80]{1})|([\x01-\x80]{1}))'



#Regexes for record payload content
nothing = r''
strings = r'([\x20-\xff]*?)'
strings_not_null = r'([\x20-\xff]+?)'
numbers = r'([\x00-\xff]{0,9})'
numbers_not_null = r'([\x00-\xff]{1,9})'
floating = r'([\x00-\xff]{0,9})'
floating_not_null = r'([\x00-\xff]{1,9})'
everything = r'([\x00-\xff]*?)'
everything_not_null = r'([\x00-\xff]+?)'




#For every type of every column of every table in the config.json file, replace it with a generic identifying
types_sub = {'(INTEGER PRIMARY KEY)':'zero', '((INT)(?!.*NO.*NULL))':'integer', '((INT)(.*NO.*NULL))':'integer_not_null', 
'(BOOL(?!.*NO.*NULL))':'boolean', '(BOOL.*NO.*NULL)':'boolean_not_null', '((CHAR|TEXT|CLOB)(?!.*NO.*NULL))':'text', 
'((CHAR|TEXT|CLOB)(.*NO.*NULL))':'text_not_null', '((BLOB|GUID|UUID)(?!.*NO.*NULL))':'blob', '((BLOB|GUID|UUID)(.*NO.*NULL))':'blob_not_null',
'((REAL|DOUB|FLOA)(?!.*NO.*NULL))':'real', '((REAL|DOUB|FLOA)(.*NO.*NULL))':'real_not_null',
'((NUMERIC|JSON)(?!.*NO.*NULL)(?!.*DATE))':'numeric', '((NUMERIC|JSON)(?!.*DATE)(.*NO.*NULL))':'numeric_not_null',
'((DATE)(?!.*NO.*NULL))':'numeric_date', '((DATE)(.*NO.*NULL))':'numeric_date_not_null'}

#After conversion of types, if there is still an unknown type (not on this types_list) left, replace it with "numeric" or "numeric_not_null"
types_list = ('zero', 'integer', 'integer_not_null', 'boolean', 'boolean_not_null', 'real', 'real_not_null', 'text', 'text_not_null',
'numeric', 'numeric_not_null', 'numeric_date', 'numeric_date_not_null', 'blob', 'blob_not_null')

#Replace each column type by its specific regex above
dict_types = {'zero':zero, 'integer':integer, 'integer_not_null':integer_not_null, 'boolean':boolean, 'boolean_not_null':boolean_not_null, 
'real':real, 'real_not_null':real_not_null, 'blob':blob, 'blob_not_null':blob_not_null, 'text':text, 'text_not_null':text_not_null,
'numeric_date':numeric_date, 'numeric_date_not_null':numeric_date_not_null, 'numeric':numeric, 'numeric_not_null':numeric_not_null}

#Replace each record payload by a specific regex per column type
dict_payload = {'zero':nothing, 'integer':numbers, 'integer_not_null':numbers_not_null, 'boolean':nothing, 'boolean_not_null':nothing,
'real':floating, 'real_not_null':floating_not_null, 'blob':everything, 'blob_not_null':everything_not_null, 'text':strings, 'text_not_null':strings_not_null, 
'numeric':everything, 'numeric_not_null':everything_not_null, 'numeric_date':everything, 'numeric_date_not_null':everything_not_null}

#Types that have a fixed min/max size in bytes VS types with variable size
multiple_bytes = ('text', 'text_not_null', 'numeric_date', 'numeric_date_not_null', 'numeric', 'numeric_not_null', 'blob', 'blob_not_null')
fixed_bytes = ('zero', 'boolean', 'boolean_not_null', 'integer', 'integer_not_null', 'real', 'real_not_null')




#Function that decodes Huffman coding
def huffmanEncoding(x,y):
    x = int(x)
    z = (x-128)*128
    a = z + int(y)
    
    return(hex(a))




#Function that translates argument provided by user as True or False
def true_false(answer):
    #If user gives a boolean argument (True/False)
    if isinstance(answer, bool):
        return(answer)
    #Elif user gives another argument that can be interpreted as True/False
    elif answer.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif answer.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    #Else it's not a valid argument
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')




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




#Function that builds regexes for each table, concatenating regexes of the header of the record with the regexes of each column type
def build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern, headers_patterns, payloads_patterns, list_fields, lists_fields, regex_constructs, tables_regexes, starts_headers, scenario, freeblock=bool):
    
    #Header pattern copy to know each column type aften construction of regex
    headers_patterns_copy = []
    
    #Until number of columns per table
    j=0
    
    #For each table
    for i in range(len(fields_numbers)):
        
        #While the length of the header is smaller than the number of columns of a given table
        while len(header_pattern) < fields_numbers[i]:
            
            #Append column type to header
            fields_types_ = fields_types[j]
            #Replace each type with its specific regex : e.g. ['INTEGER NOT NULL', 'INTEGER', 'LONGVARCHAR'] --> #e.g. ['integer_not_null', 'integer', 'text']
            fields_types_ = regex_types(fields_types_)
            #If it's an unknown type, replace it with "numeric" or "numeric_not_null" --> can be anything
            if fields_types_ not in types_list:
                if 'NOT NULL' in fields_types_:
                    fields_types_ = 'numeric_not_null'
                else:
                    fields_types_ = 'numeric'
            #Add each column type to the header_pattern list to create a header pattern per table
            header_pattern.append(fields_types_)
            j+=1
        
        #List of header patterns of all tables and its copy
        headers_patterns.append(header_pattern)
        header_pattern_copy = header_pattern.copy()
        headers_patterns_copy.append(header_pattern_copy)
        
        #Make a copy of the list to use it for the record payload regex search
        payload_pattern = copy.deepcopy(header_pattern)
        payloads_patterns.append(payload_pattern)
        
        #Empty header pattern list to move forward to the next table
        header_pattern = []


    #Until number of columns per table
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
    payload_min_max, freeblock_min_max, array_min_max = [], [], []
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
            
            #We can still compute a minimum freeblock/payload length, based on the number of columns and types
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
                #The maximum is 0xff, same for first byte, since freeblock is on 2-bytes --> min x00{min}, max xffff
                
                #If scenario == 1, payload length is of 1 byte --> maximum freeblock length is 130 (x0082)
                if scenario == 1:
                    freeblock_length = rf'(([\x00]{{1}}[\x{fb_min}-\x82]{{1}}))'
                
                #If scenario == 2, payload length may be of 2 bytes --> maximum freeblock length is 16'386 (x4002)
                elif scenario == 2:
                    freeblock_length = rf'(([\x01-\x39]{{1}}[\x00-\xff]{{1}})|([\x40]{{1}}[\x00-\x02]{{1}})|([\x00]{{1}}[\x{fb_min}-\xff]{{1}}))'
                
                #Else, can be anything and we only know the minimum
                else:
                    freeblock_length = rf'(([\x00]{{1}}[\x{fb_min}-\xff]{{1}})|([\x01-\xff]{{1}}[\x00-\xff]{{1}}))'
                
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
                
                #If min > max, then min = max, otherwise false range
                condition_min = '0x' + str(count_min)
                if int(condition_min, 16) > 0x80:
                    count_min = str(80)
                
                #Regex for the payload length, with different min size according to table
                payload_length = rf'((([\x81-\xff]{{1,8}}[\x00-\x80]{{1}})|([\x{count_min}-\x80]{{1}})){{1}})'
                
                #Add the regex to a list of payload lengths regexes
                payload_min_max.append(payload_length)
                #Set min back to 1 (the minimum is 1 byte to count the 1-byte for the length of the serial types array)
                count_min = 1
        


        """REGEX FOR SERIAL TYPES ARRAY MIN/MAX LENGTH"""

        #If the record is not overwritten by a freeblock (intact) 
        #Or if it is but by scenarios 3, 4 & 5 (we still recover part or the entire byte of serial types array length)
        #In scenarios 1 & 2, this array length is completely overwritten
        if (not freeblock) or (scenario == 3) or (scenario == 4) or (scenario == 5):
            
            #We have a min serial types array length by adding 1 to the minimum array length for each element (column type) of the header
            for element in header_pattern:
                counter_min += 1
                #If the column type is not of a fixed min/max size, add 9 to the maximum array length
                if element in multiple_bytes:
                    counter_max += 9
                #If the column type is of a fixed min/max size, only add 1 to the maximum array length
                else:
                    counter_max += 1
            
            #If the table has more than 128 columns (0x80, max on 1-byte, then Huffman encoding on 2-bytes)
            if counter_max > 128:
                #First byte : this only handles x81xx cases, so until 256 columns
                x = 129
                #Last byte maximum (last byte minimum is 00, e.g. x8100 = 129)
                y = 128
                
                #Fill it to a "two-digits" hex number
                counter_min = format(counter_min,'x').zfill(2)
                counter_max = format(128,'x').zfill(2)
                x = format(x,'x').zfill(2)
                y = format(y,'x').zfill(2)

                #If min > max, then min = max, otherwise impossible range
                cond_min = '0x' + str(counter_min)
                cond_max = '0x' + str(counter_max)

                if int(cond_min, 16) > int(cond_max, 16):
                    counter_min = counter_max
                
                #In scenario 4, half of the array length is overwritten --> the minimum for the eventual second byte is 00 
                if scenario == 4:
                    counter_min = format(0,'x').zfill(2)

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
            
            #Set min and max back to 1 (we have at least one column per table to have potential records on it)
            counter_min = 1
            counter_max = 1


        
        #We don't want records which header only has zeroes, otherwise it's almost empty and we have a lot of false positives matches
        #For that we use a negative lookahead assertion regex before the header regex
        #For example, Isaac (?!Asimov) will match 'Isaac ' only if it’s not followed by 'Asimov'.
        #Negative lookahead assertions have to be of precise length, so we use the number of types 
        #(e.g. if a table has 5 columns, we don't want all 5 types length to be zeroes)
        #We only do that to overwritten records, so that all the intact records (scenario 0) are recovered

        #Number of types used 
        types_length = len(header_pattern)

        #If type1 of the array is overwritten (scenario 1), remove type1 from header pattern and surround header group by () and by the negative lookahead assertion
        #Type1 is missing --> types_length-1
        if scenario == 1:
            header_pattern[0] = rf'(?![\x00|\x0c|\x0d|\x08|\x09]{{{types_length-1}}})'
            header_pattern.insert(1, ')')
            header_pattern.insert(2, '(')
            header_pattern.insert(len(header_pattern), ')')
        
        #For other scenarios, type1 is not missing --> types_length
        elif scenario == 2 or scenario == 3 or scenario == 4 or scenario == 5:
            header_pattern.insert(0, rf'(?![\x00|\x0c|\x0d|\x08|\x09]{{{types_length}}})')
            header_pattern.insert(1, ')')
            header_pattern.insert(2, '(')
            header_pattern.insert(len(header_pattern), ')')

        #Else, if scenario 0, find anything even records with less information and surround header group by ()
        else:
            header_pattern.insert(0, rf'(?![\x00]{{{types_length}}})')
            header_pattern.insert(1, ')')
            header_pattern.insert(2, '(')
            header_pattern.insert(len(header_pattern), ')')

    

    #Build a start of header according to each scenario and add it to a list of start headers
    #If the record is overwritten by a freeblock
    if freeblock:
        #Freeblock overwrites record until the rowid, so we recover from the serial types array length
        if scenario == 3:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['((', next_freeblock, freeblock_min_max[index], array_min_max[index], ')'])
                starts_headers.append(start_header)
        #Freeblock overwrites record until part of the serial types array length, so we recover part of it
        elif scenario == 4:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['((', next_freeblock, freeblock_min_max[index], array_min_max[index], ')'])
                starts_headers.append(start_header)
        #Freeblock overwrites record until part of the rowid, so we recover part of it
        elif scenario == 5:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['((', next_freeblock, freeblock_min_max[index], row_id, array_min_max[index], ')'])
                starts_headers.append(start_header)
        #Freeblock overwrites record until type1 or until array length, so we recover from type2 or type1
        elif scenario == 1 or scenario == 2:
            for index in range(len(freeblock_min_max)):
                start_header = "".join(['((', next_freeblock, freeblock_min_max[index], ')'])
                starts_headers.append(start_header)
    
    #If the record is not overwritten by a freeblock (intact)
    else:
        for index in range(len(payload_min_max)):
            start_header = "".join(['((', payload_min_max[index], row_id, array_min_max[index], ')'])
            starts_headers.append(start_header)

    

    #Concerning record payload (content)
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
            payload_pattern.append(rf'.*{hex_str}')
        
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
        payload_pattern.insert(0, '(?=')
        payload_pattern.insert(len(payload_pattern), ')')
    
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



    #Link together in a dict the table name, columns names, types identifyings and the whole regex for that table
    for i in range(len(regex_constructs)):
        
        table_regex = {tables_names[i]:[lists_fields[i], headers_patterns_copy[i], regex_constructs[i]]}
        
        #Add some information columns before the real table columns to specify the file from which the record is carved, its offset on the file and the scenario
        for table, fields_regex in table_regex.items():
            fields_regex[0].insert(0, 'carved_record_file')
            fields_regex[0].insert(0, 'carved_record_offset')
            fields_regex[0].insert(0, 'carving_scenario_number')

        #Append to tables_regexes list
        tables_regexes.append(table_regex)

    #Return list of linked table name, columns names, types identifyings and the whole regex for that table
    return tables_regexes




#Function that iterates regexes over file, finds matches and adds them to matches list
def find_matches(mainfile, open_file, table, fields_regex, scenario):
    
    #Variables to pass to decode_unknown_header function
    unknown_header, unknown_header_2, limit, matches = [], [], [], []
    if scenario==0:
        len_start_header = 3
        freeblock = False
    elif scenario == 1 or scenario == 2:
        len_start_header = 2
        freeblock = True
    elif scenario == 3 or scenario == 4:
        len_start_header = 3
        freeblock = True
    elif scenario == 5:
        len_start_header = 4
        freeblock = True

    #Open mainfile in binary format and reading mode
    with open(open_file, 'r+b') as file:
        
        #Iterate over the file (mm)    
        #mmap: file is mapped in memory and its content is internally loaded from disk as needed
        #instead of file.read() or file.readlines(), improves performance speading up the reading of files
        mm = mmap.mmap(file.fileno(), length=0, access=mmap.ACCESS_READ)
            
        #Search and process each match
        #Update regex module : since regex 2021.4.4 : overlapped=True finds overlapping matches (match starting at an offset inside another match)
        for match in re.finditer(fields_regex[2], mm, overlapped=True, concurrent=True):
            
            #Start and end of match
            a = match.start()
            b = match.end()
            
            #Append match and related variables to list of matches
            matches.append((a, b, mainfile, open_file, table, fields_regex, unknown_header, unknown_header_2, limit, scenario, len_start_header, freeblock))
        
        #Free the memory
        mm.close()
    
    #Close mainfile
    file.close()

    #Return list of matches and related variables
    return [matches]




#Function that decodes bytes from potential true header into integers (so that we can do calculations on it afterwards) and appends them to unknown_header list
def decode_unknown_header(a, b, mainfile, open_file, table, fields_regex, unknown_header, unknown_header_2, limit, scenario, len_start_header, freeblock):
    
    #Variables to pass to filter_records function
    unknown_header, unknown_header_2, limit, payload = [], [], [], []
    
    record_infos_2 = str(mainfile)

    if scenario == 0:
        record_infos_0 = 'Scenario 0 : non-deleted or non-overwritten (journal files) records'
        z=3
    elif scenario == 1:
        record_infos_0 = 'Scenario 1 : deleted records overwritten until type 2'
        z=2
    elif scenario == 2:
        record_infos_0 = 'Scenario 2 : deleted records overwritten until type 1'
        z=2
    elif scenario == 3:
        record_infos_0 = 'Scenario 3 : deleted records overwritten until serial types array length'
        z=3
    elif scenario == 4:
        record_infos_0 = 'Scenario 4 : deleted records overwritten until part of serial types array length'
        z=3
    elif scenario == 5:
        record_infos_0 = 'Scenario 5 : deleted records overwritten until part of rowid'
        z=4
    

    #Open mainfile in binary format and reading mode
    with open(open_file, 'r+b') as mm:
        
        #Until end of the match
        count = 0

        #Go to start of the match
        mm.seek(a)
        
        #If the record is overwritten by a freeblock, read 2 bytes (next freeblock offset) then 2 bytes (length of this freeblock)
        if freeblock:
            byte = int(struct.unpack('>H', mm.read(2))[0])
            unknown_header.append(byte)
            unknown_header_2.append(byte)
            count+=2
            
            byte = int(struct.unpack('>H', mm.read(2))[0])
            unknown_header.append(byte)
            unknown_header_2.append(byte)
            count+=2


        #While not end of the match
        while count <= (b-a-1):
            
            #Before serial types part (start header length): append(byte) to unknown_header
            if len(unknown_header) < len_start_header:

                #Read byte by byte, convert in integer, and append to unknown_header list
                byte = int(struct.unpack('>B', mm.read(1))[0])
               
                #If byte < 0x80
                if byte < 128:
                    unknown_header.append(byte)
                    unknown_header_2.append(byte)
                    count+=1
                
                #Else, handle Huffman encoding until 9 successive bytes
                else:
                    cont1 = int(struct.unpack('>B', mm.read(1))[0])
                    byte1 = int(huffmanEncoding(byte, cont1),16)
                    if cont1 < 128:
                        unknown_header.append(byte1)
                        unknown_header_2.append(byte1)
                        count+=2
                    else:
                        cont2 = int(struct.unpack('>B', mm.read(1))[0])
                        byte2 = int(huffmanEncoding(byte1, cont2),16)
                        count+=2
                        if cont2 < 128:
                            unknown_header.append(byte2)
                            unknown_header_2.append(byte2)
                            count+=1
                        else:
                            count+=1
                            cont3 = int(struct.unpack('>B', mm.read(1))[0])
                            byte3 = int(huffmanEncoding(byte2, cont3),16)
                            if cont3 < 128:
                                unknown_header.append(byte3)
                                unknown_header_2.append(byte3)
                                count+=1
                            else:
                                count+=1
                                cont4 = int(struct.unpack('>B', mm.read(1))[0])
                                byte4 = int(huffmanEncoding(byte3, cont4),16)
                                if cont4 < 128:
                                    unknown_header.append(byte4)
                                    unknown_header_2.append(byte4)
                                    count+=1
                                else:
                                    count+=1
                                    cont5 = int(struct.unpack('>B', mm.read(1))[0])
                                    byte5 = int(huffmanEncoding(byte4, cont5),16)
                                    if cont5 < 128:
                                        unknown_header.append(byte5)
                                        unknown_header_2.append(byte5)
                                        count+=1
                                    else:
                                        count+=1
                                        cont6 = int(struct.unpack('>B', mm.read(1))[0])
                                        byte6 = int(huffmanEncoding(byte5, cont6),16)
                                        if cont6 < 128:
                                            unknown_header.append(byte6)
                                            unknown_header_2.append(byte6)
                                            count+=1
                                        else:
                                            count+=1
                                            cont7 = int(struct.unpack('>B', mm.read(1))[0])
                                            byte7 = int(huffmanEncoding(byte6, cont7),16)
                                            if cont7 < 128:
                                                unknown_header.append(byte7)
                                                unknown_header_2.append(byte7)
                                                count+=1
                                            else:
                                                count+=1
                                                cont8 = int(struct.unpack('>B', mm.read(1))[0])
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
                
                #Append limit to list of limits to know how many bytes takes the start of the header (because 3 integers are not necessarily only 3 bytes)
                limit.append(count)
                
                #Read byte by byte, convert in integer, and append to unknown_header list
                byte = int(struct.unpack('>B', mm.read(1))[0])
                
                #If byte < 0x80
                if byte < 128:
                    unknown_header.append(serialTypes(byte))
                    unknown_header_2.append(byte)
                    count+=1
                
                #Else, handle Huffman encoding until 9 successive bytes
                else:
                    cont1 = int(struct.unpack('>B', mm.read(1))[0])
                    byte1 = int(huffmanEncoding(byte, cont1),16)
                    if cont1 < 128:
                        unknown_header.append(serialTypes(byte1))
                        unknown_header_2.append(byte1)
                        count+=2
                    else:
                        cont2 = int(struct.unpack('>B', mm.read(1))[0])
                        byte2 = int(huffmanEncoding(byte1, cont2),16)
                        count+=2
                        if cont2 < 128:
                            unknown_header.append(serialTypes(byte2))
                            unknown_header_2.append(byte2)
                            count+=1
                        else:
                            count+=1
                            cont3 = int(struct.unpack('>B', mm.read(1))[0])
                            byte3 = int(huffmanEncoding(byte2, cont3),16)
                            if cont3 < 128:
                                unknown_header.append(serialTypes(byte3))
                                unknown_header_2.append(byte3)
                                count+=1
                            else:
                                count+=1
                                cont4 = int(struct.unpack('>B', mm.read(1))[0])
                                byte4 = int(huffmanEncoding(byte3, cont4),16)
                                if cont4 < 128:
                                    unknown_header.append(serialTypes(byte4))
                                    unknown_header_2.append(byte4)
                                    count+=1
                                else:
                                    count+=1
                                    cont5 = int(struct.unpack('>B', mm.read(1))[0])
                                    byte5 = int(huffmanEncoding(byte4, cont5),16)
                                    if cont5 < 128:
                                        unknown_header.append(serialTypes(byte5))
                                        unknown_header_2.append(byte5)
                                        count+=1
                                    else:
                                        count+=1
                                        cont6 = int(struct.unpack('>B', mm.read(1))[0])
                                        byte6 = int(huffmanEncoding(byte5, cont6),16)
                                        if cont6 < 128:
                                            unknown_header.append(serialTypes(byte6))
                                            unknown_header_2.append(byte6)
                                            count+=1
                                        else:
                                            count+=1
                                            cont7 = int(struct.unpack('>B', mm.read(1))[0])
                                            byte7 = int(huffmanEncoding(byte6, cont7),16)
                                            if cont7 < 128:
                                                unknown_header.append(serialTypes(byte7))
                                                unknown_header_2.append(byte7)
                                                count+=1
                                            else:
                                                count+=1
                                                cont8 = int(struct.unpack('>B', mm.read(1))[0])
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

        
        #Return list of unknown headers and related variables
        return [a, b, table, fields_regex, unknown_header, unknown_header_2, limit, open_file, payload, record_infos_0, str(a), record_infos_2, scenario, z]






#Function that keeps potential records and discard the rest
def filter_records(a, b, table, fields_regex, unknown_header, unknown_header_2, limit, open_file, payload, record_infos_0, record_infos_1, record_infos_2, scenario, z):
    
    #Payload content to fill
    payload = []

    #Return potential records header and related variables
    return_value = [b, table, fields_regex, unknown_header, unknown_header_2, open_file, payload, record_infos_0, record_infos_1, record_infos_2, scenario, z]

    #Open mainfile in binary format and reading mode
    with open(open_file, 'r+b') as mm:
        
        #If limit is an empty list, header only contains start of header and is therefore a non-valid header
        if not limit:
            pass
        
        #Else: may be a valid header
        else:
            
            #For each scenario
            
            #If scenario == 0
            #If the payload length is equal to the sum of each type length plus the length of the serial types array AND the sum of all types is not equal to 0
            #AND the serial types array length is equal to the number of bytes from the serial types array length 
            #AND the length of the header is > 3 (payload length, rowid, serial types array length, type1)
            if (scenario==0) and ((unknown_header[0] == sum(unknown_header[2:])) and (sum(unknown_header[3:]) != 0) and (len(unknown_header) > 3) and ((b-a-limit[0]) == ((unknown_header[2]-1) or (unknown_header[2]-2)))):
                    if return_value != '':
                        return return_value
            


            #If scenario == 1
            #Then we have to assume what type1 is since it's overwritten (the regex is [next freeblock, actual freeblock length, type2])
            #WARNING: more false positives because more options
            #WARNING: more duplicates if 2 or more tables with same number of columns --> will try for each potential type1
            
            #If type1 is an integer or a floating, then a number from 0-9 is missing on first position on the header
            elif ((scenario==1) and ((fields_regex[1])[0] == 'integer' or (fields_regex[1])[0] == 'integer_not_null' or (fields_regex[1])[0] == 'real' or (fields_regex[1])[0] == 'real_not_null') and (((sum(unknown_header[2:]) + (b-a)) <= unknown_header[1] <= (sum(unknown_header[2:]) + (b-a) + 9)))):
                
                #x is the unknown integer
                x = unknown_header[1] - sum(unknown_header[2:]) - (b-a)
                
                if x >= 0:
                    #Insert it on third place of the header because type1 follows the freeblock in this scenario
                    unknown_header.insert(2, x)
                    if return_value != '':
                        return return_value
    

            #If type1 is an integer primary key, then a 0 is missing on first position on the header
            elif ((scenario==1) and ((fields_regex[1])[0] == 'zero') and ((sum(unknown_header[2:]) + (b-a+1)) == unknown_header[1])):
                x = 0
                unknown_header.insert(2, x)
                if return_value != '':
                    return return_value
            
    
            #If type1 is boolean, then a 8=0 or a 9=1 is missing on first position on the header
            #Since the 8 or 9 information is enough, we don't find it further on the record payload, so it doesn't change its length (x=0)
            #So, if it was overwritten as type1, we cannot know if it was a 8 or a 9 (True or False) --> not recovered
            elif ((scenario==1) and ((fields_regex[1])[0] == 'boolean' or (fields_regex[1])[0] == 'boolean_not_null') and ((sum(unknown_header[2:]) + (b-a+1)) == unknown_header[1])):
                x = 0
                unknown_header.insert(2, x)
                if return_value != '':
                    return return_value
                    
            
            #If type1 is a blob, then an even number is missing on first position on the header
            elif ((scenario==1) and ((fields_regex[1])[0] == 'blob' or (fields_regex[1])[0] == 'blob_not_null') and ((unknown_header[1] - ((sum(unknown_header[2:]) + (b-a+1)))) % 2 == 0)):
                x = (unknown_header[1] - ((sum(unknown_header[2:]) + (b-a+1))))
                if x >= 0:
                    unknown_header.insert(2, x)
                    if return_value != '':
                        return return_value
                    

            #If type1 is a text, then an odd number is missing on first position on the header
            elif ((scenario==1) and ((fields_regex[1])[0] == 'text' or (fields_regex[1])[0] == 'text_not_null') and ((unknown_header[1] - ((sum(unknown_header[2:]) + (b-a+1)))) % 2 != 0)):
                x = (unknown_header[1] - ((sum(unknown_header[2:]) + (b-a+1))))
                if x >= 0:
                    unknown_header.insert(2, x)
                    if return_value != '':
                        return return_value
                    

            #Else, if type1 is a numeric, a numeric not null, a numeric date or a numeric date not null, then the value can be anything
            elif ((scenario==1) and ((fields_regex[1])[0] == 'numeric' or (fields_regex[1])[0] == 'numeric_not_null' or (fields_regex[1])[0] == 'numeric_date' or (fields_regex[1])[0] == 'numeric_date_not_null')):
                x = (unknown_header[1] - ((sum(unknown_header[2:]) + (b-a+1))))
                if x >= 0:
                    unknown_header.insert(2, x)
                    if return_value != '':
                        return return_value



            #If scenario == 2
            #WARNING: false positives with 1 and 2-columns headers that can easily match
            
            #If the freeblock length is equal to the sum of each type length plus the length of the serial types array
            #AND the sum of all types is not equal to
            elif (scenario == 2) and (((sum(unknown_header[2:]) + (b-a)) == (unknown_header[1])) and ((sum(unknown_header[2:]) != 0))):
                if return_value != '':
                    return return_value



            #If scenario == 3
            
            #If the freeblock length is equal to the sum of each type length plus the length of the serial types array
            #AND the sum of all types is not equal to 0 AND the length of the header is > 3 (next fb, actual fb, serial types array length, type1)
            elif (scenario == 3) and (((sum(unknown_header[2:]) + 4) == (unknown_header[1])) and ((sum(unknown_header[2:]) != 0)) and (len(unknown_header) > 3)):
                if return_value != '':
                    return return_value



            #If scenario == 4
            #We assume serial types array length cannot be > 2 bytes, otherwise too much columns, so here 1 byte is overwritten, 1 not
            
            #If the second part of the serial types array length is < than 128 (if it's > 128, it's not a second part of the serial types array length)
            #AND if the freeblock length is NOT equal to the sum of each type length plus the length of PART of the serial types array
            #AND the freeblock length is equal to the sum of each type length plus the length until serial types plus the length in bytes of serial types
            #AND the sum of all types is not equal to 0 AND the length of the header is > 3 (next fb, actual fb, part of serial types array length, type1)
            elif (scenario == 4) and (((sum(unknown_header[2:]) + 4) != (unknown_header[1])) and (unknown_header[2] < 128) and (unknown_header[1] == (sum(unknown_header[2:])+128+4-1)) and (len(unknown_header) > 3)):
                if return_value != '':
                    return return_value
            


            #If scenario == 5
            #This scenario also covers SCENARIO 6 : if payload length is 4 bytes --> record starts at rowid
            #As rowid can be anything from 1-9 bytes, starting at part of it or starting at the start of rowid does not change anything
            #If payload length is exactly 4 bytes or more in length, the record is greater than 512MB, which is rare
            
            #If the freeblock length is equal to the sum of each type length plus the length until serial types
            #AND the sum of all types is not equal to 0 AND the length of the header is > 4 (next fb, actual fb, part of rowid, serial types array length, type1)
            elif (scenario == 5) and ((unknown_header[1] == (sum(unknown_header[3:])+(limit[0]-1))) and ((sum(unknown_header[3:]) != 0)) and (len(unknown_header) > 3)):
                if return_value != '':
                    return return_value
            
            

            #Else, discard record
            else:
                return None




#Function that decodes the record payload based on the possible headers
def decode_record(b, table, fields_regex, unknown_header, unknown_header_2, open_file, payload, record_infos_0, record_infos_1, record_infos_2, scenario, z):
    
    #Open mainfile in binary format and reading mode
    with open(open_file, 'r+b') as mm:
    
        #Go to the end of the match to start reading payload content that comes just after the header/match
        mm.seek(b)
        
        #For each field's length of the record
        for l in ((unknown_header)[z:]):
            
            #Read bytes for that length and decode it according to encoding : 
            #e.g. potential header = [48, 42, 8, 0, 24, 7, 1, 0, 8, 0] 
            #--> read the following number of bytes from type1 [0, 24, 7, 1, 0, 8, 0]
            payload_field = mm.read(l)
            
            #Append the content to payload list :
            #e.g. [0, 24, 7, 1, 0, 8, 0] --> ['', 'https://www.youtube.com/', 'YouTube', 3, '', 13263172804027223, '']
            payload.append(payload_field)


        try:
            #For each identifying type per column
            for n,i in enumerate(fields_regex[1]):
                
                #If type is zero (INTEGER PRIMARY KEY = alias for rowid)
                if i == 'zero':
                    #Then if the record is intact we can retrieve the rowid from the header (second place)
                    if scenario == 0:
                        try:
                            payload[n] = unknown_header[1]
                        except IndexError:
                            pass
                    #For other scenarios, the rowid is mostly/entirely overwritten
                    else:
                        payload[n] = 'rowid not recovered'
                
                #If type is a boolean or integer or real
                elif i == 'boolean' or i == 'boolean_not_null' or i == 'integer' or i == 'integer_not_null' or i == 'real' or i == 'real_not_null':
                    #Then convert bytes into integers
                    try:
                        payload[n] = int.from_bytes(payload[n], byteorder='big', signed=True)
                    except IndexError:
                        pass
                    

                    #Since for scenario 1 type1 is missing in unknown_header_2 but not in unknown_header (it has been added), we have to go one index back
                    if scenario == 1:
                        z = 1
                    
                    #If in unknown_header_2 not decoded there was a 7, then it's a floating point
                    #If there was an 8, then it's a 0 in the record
                    #If there was a 9, then it's a 1 in the record
                    try:
                        
                        if unknown_header_2[z+n] == 7:
                            #Convert to binary
                            payload[n] = bin(payload[n])
                            #Unpack as 8-bytes floating point
                            payload[n] = struct.unpack('!d', struct.pack('!q', int(payload[n], 2)))[0]
                        
                        elif unknown_header_2[z+n] == 8:
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
                
            
                #For other types, decode it as a string from utf-8
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


        #Add information to information columns before the real table columns to specify the file from which the record is carved, its offset on the file and the scenario
        payload.insert(0, record_infos_2)
        payload.insert(0, record_infos_1)
        payload.insert(0, record_infos_0)


        #For overwritten boolean values in scenario 1, we cannot know if True or False
        if scenario == 1 and ((fields_regex[1])[0] == 'boolean' or (fields_regex[1])[0] == 'boolean_not_null'):
            payload[3] == 'boolean value not recovered'

        
        #If record contains the same number of columns as the table it matched with, append its INSERT statement to statements list
        if len(fields_regex[0]) == len(payload):
            #For columns' special names escaped with [], it must be removed to make an insert
            fields_tuple = str(tuple(fields_regex[0]))
            fields_tuple = fields_tuple.replace('[', '')
            fields_tuple = fields_tuple.replace(']', '')
            statement = "".join(["INSERT INTO", " ", table, fields_tuple, " VALUES ", str(tuple(payload))])

            #Return the INSERT STATEMENT to write to output database
            return statement




#Main function with command-line arguments 
def main(args):

    #Retrieve argument user provided for --linked
    linked = true_false(args.linked)

    #Retrieve config.json file, files or directory of files given as input

    #List of --config files and list of their paths
    config_files, config_files_paths = [], []

    #If it's a directory
    if os.path.isdir(args.config[0]):
        #Look for files inside
        for parent, dirnames, filenames in os.walk(args.config[0]):
            for fn in filenames:
                #Search for every config.json file
                if fn.startswith('config_') and fn.endswith('.json'):
                    #For each config.json file, append their name to config_files list and path to config_files_paths list
                    filepath = os.path.join(parent, fn)
                    config_files.append(fn)
                    config_files_paths.append(filepath)
        #Convert the directory given as --config in a list of each config.json file path
        args.config = config_files_paths
    #If it's file(s)
    elif os.path.isfile(args.config[0]):
        #Append their name to config_files list
        args.config = args.config
    #Else, nor file nor directory
    else:
        print('\n\n', "Nor file(s) nor directory", '\n\n')



    #For each config file provided as --config (can be in a directory)
    for configfile in args.config:
        
        #List of --input files, list of their paths, list of CREATE statements to create output database, list of INSERT statements to insert records in output database
        main_files, main_files_paths, create_statements, statements = [], [], [], []
        
        #Open each config.json file provided containing db infos, each table, column and type of column
        with open(configfile, 'r') as config_file:
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

        
        #Retrieve file, files or directory given as input
        #For each file provided as input
        for mainfile in args.input:
            #If it's a directory
            if os.path.isdir(mainfile):
                #Look for files inside
                for parent, dirnames, filenames in os.walk(mainfile):
                    #If we want to search only on files linked to database used to create config.json
                    if linked:
                        #Search for linked files with same name as main database name (e.g. if mmssms.db, search for mmssms.db, mmssms.db-journal, mmssms.db-wal, etc.)
                        for fn in filenames:
                            start = configfile.find('config_') + len('config_')
                            end = configfile.find('.json')
                            linked_file = configfile[start:end]
                            #For each linked file, append their name to main_files list and path to main_files_paths list
                            if linked_file in fn:
                                filepath = os.path.join(parent, fn)
                                main_files.append(fn)
                                main_files_paths.append(filepath)
                    #If we want to search on all files (not only linked ones)
                    else:
                        for fn in filenames:
                            filepath = os.path.join(parent, fn)
                            main_files.append(fn)
                            main_files_paths.append(filepath)
            #If it's file(s)
            elif os.path.isfile(mainfile):
                #If we want to search only on files linked to database used to create config.json
                if linked:
                    start = configfile.find('config_') + len('config_')
                    end = configfile.find('.json')
                    linked_file = configfile[start:end]
                    if linked_file in mainfile:
                        main_files.append(mainfile)
                    else:
                        print('\n\n', str(configfile), 'is not linked to', str(mainfile), '\n\n')
                #If we want to search on all files (not only linked ones)
                else:
                    #Append their name to main_files list
                    main_files.append(mainfile)
            #Else, nor file nor directory
            else:
                print('\n\n', "Nor file(s) nor directory", '\n\n')




        """Build regexes for each scenario (intact records VS overwritten records according to each scenario)"""

        #Scenario 0
        header_pattern, headers_patterns, payloads_patterns, regex_constructs, tables_regexes, list_fields, lists_fields, starts_headers = [], [], [], [], [], [], [], []
        build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern, headers_patterns, payloads_patterns, list_fields, lists_fields, regex_constructs, tables_regexes, starts_headers, scenario=0, freeblock=False)

        #Scenario 1
        header_pattern_s1, headers_patterns_s1, payloads_patterns_s1, regex_constructs_s1, tables_regexes_s1, list_fields_s1, lists_fields_s1, starts_headers_s1 = [], [], [], [], [], [], [], []
        build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern_s1, headers_patterns_s1, payloads_patterns_s1, list_fields_s1, lists_fields_s1, regex_constructs_s1, tables_regexes_s1, starts_headers_s1, scenario=1, freeblock=True)

        #Scenario 2
        header_pattern_s2, headers_patterns_s2, payloads_patterns_s2, regex_constructs_s2, tables_regexes_s2, list_fields_s2, lists_fields_s2, starts_headers_s2 = [], [], [], [], [], [], [], []
        build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern_s2, headers_patterns_s2, payloads_patterns_s2, list_fields_s2, lists_fields_s2, regex_constructs_s2, tables_regexes_s2, starts_headers_s2, scenario=2, freeblock=True)

        #Scenario 3
        header_pattern_s3, headers_patterns_s3, payloads_patterns_s3, regex_constructs_s3, tables_regexes_s3, list_fields_s3, lists_fields_s3, starts_headers_s3 = [], [], [], [], [], [], [], []
        build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern_s3, headers_patterns_s3, payloads_patterns_s3, list_fields_s3, lists_fields_s3, regex_constructs_s3, tables_regexes_s3, starts_headers_s3, scenario=3, freeblock=True)

        #Scenario 4
        header_pattern_s4, headers_patterns_s4, payloads_patterns_s4, regex_constructs_s4, tables_regexes_s4, list_fields_s4, lists_fields_s4, starts_headers_s4 = [], [], [], [], [], [], [], []
        build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern_s4, headers_patterns_s4, payloads_patterns_s4, list_fields_s4, lists_fields_s4, regex_constructs_s4, tables_regexes_s4, starts_headers_s4, scenario=4, freeblock=True)

        #Scenario 5
        header_pattern_s5, headers_patterns_s5, payloads_patterns_s5, regex_constructs_s5, tables_regexes_s5, list_fields_s5, lists_fields_s5, starts_headers_s5 = [], [], [], [], [], [], [], []
        build_regex(fields_numbers, fields_types, fields_names, tables_names, header_pattern_s5, headers_patterns_s5, payloads_patterns_s5, list_fields_s5, lists_fields_s5, regex_constructs_s5, tables_regexes_s5, starts_headers_s5, scenario=5, freeblock=True)




        """"Search and decode record matches in file"""

        #For each file provided as input
        #tqdm for progress bar per file processment, its description is the output database's name
        for mainfile in tqdm.tqdm(main_files, total=len(main_files), position=0, leave=True, desc=output_db):
            #If a directory is given as input
            if os.path.isdir(args.input[0]):
                #The index of file being processed is the same for its path on main_files_paths list
                index = main_files.index(mainfile)
                open_file = main_files_paths[index]
            #Else, no need for path
            else:
                open_file = mainfile
            
            
            #Open mainfile in binary format and reading mode
            with open(open_file, 'r+b') as file:

                #Variables to pass to find_matches function
                matches_args, matches_args_s1, matches_args_s2, matches_args_s3, matches_args_s4, matches_args_s5, all_matches_args = [], [], [], [], [], [], []

                #Process mainfile according to each scenario
                
                #For each regex per table
                for table_regex in tables_regexes:
                    #For each table and its fields' regexes
                    for table, fields_regex in table_regex.items():
                        #Append file name, table name, fields, regexes and scenario number to matches_args list
                        matches_args.append((mainfile, open_file, table, fields_regex, 0))
                #Append list of matches arguments to all_matches_args list
                all_matches_args.append(matches_args)
                
                for table_regex_s1 in tables_regexes_s1:
                    for table_s1, fields_regex_s1 in table_regex_s1.items():
                        matches_args_s1.append((mainfile, open_file, table_s1, fields_regex_s1, 1))
                all_matches_args.append(matches_args_s1)

                for table_regex_s2 in tables_regexes_s2:
                    for table_s2, fields_regex_s2 in table_regex_s2.items():
                        matches_args_s2.append((mainfile, open_file, table_s2, fields_regex_s2, 2))
                all_matches_args.append(matches_args_s2)
                
                for table_regex_s3 in tables_regexes_s3:
                    for table_s3, fields_regex_s3 in table_regex_s3.items():
                        matches_args_s3.append((mainfile, open_file, table_s3, fields_regex_s3, 3))
                all_matches_args.append(matches_args_s3)
                
                for table_regex_s4 in tables_regexes_s4:
                    for table_s4, fields_regex_s4 in table_regex_s4.items():
                        matches_args_s4.append((mainfile, open_file, table_s4, fields_regex_s4, 4))
                all_matches_args.append(matches_args_s4)
                
                for table_regex_s5 in tables_regexes_s5:
                    for table_s5, fields_regex_s5 in table_regex_s5.items():
                        matches_args_s5.append((mainfile, open_file, table_s5, fields_regex_s5, 5))
                all_matches_args.append(matches_args_s5)


                #For each list of matches arguments
                for matches_args in all_matches_args:

                    #Start (number of CPUs in the system - 1) worker processes
                    with multiprocessing.Pool(cpu_count()-1) as pool:

                        #Run find_matches, decode_unknown_header, filter_records, decode_record functions with pool of workers
                        #Use starmap because functions take multiple arguments

                        matches = pool.starmap(find_matches, [match_arg for match_arg in matches_args])
                        #Make a list of matches and not a list of matches per table
                        matches = [i for i in chain.from_iterable(matches) if i != []]
                        matches = [i for i in chain.from_iterable(matches) if i != []]

                        matches = pool.starmap(decode_unknown_header, [match for match in matches])
            
                        matches = pool.starmap(filter_records, matches)
                        #Remove discarded records (None)
                        matches = [x for x in matches if x != None]

                        matches = pool.starmap(decode_record, matches)

                        #Result of decode_record is a list of INSERT statements : append list to statements list
                        for statement in matches:
                            statements.append(statement)
                    
                    #Print time elapsed for each scenario processing
                    print('\n', 'Finished processing scenario %s/5 - %s seconds' % (str((matches_args[0])[4]), (time.time() - start_time)))
            
            #Close file
            file.close()




        """"Write records to output database"""

        #Connection to output database
        connection = sqlite3.connect(args.output + output_db, isolation_level=None)

        #Performance improvements
        connection.execute('PRAGMA journal_mode=OFF')
        connection.execute('PRAGMA locking_mode=EXCLUSIVE')
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("BEGIN TRANSACTION")


        #CREATE tables
        for create_statement in create_statements:

            try:
                connection.execute(create_statement)
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                print('\n\n', 'sqlite error: ', e, '\n\n')


        #INSERT records
        for final_statement in statements:
            if final_statement != None:
                #If a keyword is provided as optionnal argument
                if args.keyword:
                    #Make sure it is really present in the record (lookahead assertion sometimes matches the word after the end of the record)
                    if args.keyword in final_statement:
                        try:
                            connection.execute(final_statement)
                        except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                            print('\n\n', 'sqlite error: ', e, '\n\n')
                    else:
                        pass
                #Else, insert all records
                else:
                    try:
                        connection.execute(final_statement)
                    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                        print('\n\n', 'sqlite error: ', e, '\n\n')
            else:
                pass


        #Commit transactions and close connection to output database
        connection.commit()
        connection.close()




#Command-line arguments and options
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", nargs='+', help='Provide a config.json file generated by config.py, containing the main db schema.')
parser.add_argument("-i", "--input", nargs='+', help='Provide all the files or a directory in which you want to search for records.')
parser.add_argument("-l", "--linked", type=true_false, nargs='?', default=True, help='Parse only files linked with database used to create config.json file, True/False, True by default')
parser.add_argument("-k", "--keyword", nargs='?', required=False, help='Retrieve only records containing a certain word, e.g. --keyword http')
parser.add_argument("-o", "--output", nargs='?', help='Where do you want to save the output database file?')
args = parser.parse_args()




#Run main function with command-line arguments provided by user
if __name__ == '__main__':
    main(args)