#!/usr/bin/python3

##########      config.py     ##########
""""
This script retrieves table schemas from a database file given as argument and writes 
the database's and schema's information to a config_database.json file.
"""



import argparse, os, struct, json, mmap, itertools, copy
from fileinput import filename
import regex as re
from tqdm import tqdm
from pathlib import Path




#Regex of a CREATE TABLE statement, if it's intact (s0) and for each scenario (s1-3) if the table was deleted
#I.e. CREATE TABLE (type TEXT, name TEXT, tbl_name TEXT, rootpage INTEGR, sql statement TEXT)
#--> first column (type TEXT) is always "table" of length 0x17 (5)
regex_s0 = rb'(((([\x37-\x80]{1})|([\x81-\xff]{1}[\x00-\x80]{1}))(([\x81-\xff]{1}[\x00-\x80]{1})|([\x01-\x80]{1}))([\x06-\x0E]{1})([\x17]{1})([\x01-\x80]{1})([\x01-\x80]{1})([\x00-\x09]{1})(([\x81-\xff]{1}[\x00-\x80]{1})|([\x19-\x80]{1})))((?=(.*\x74\x61\x62\x6C\x65))))'
regex_s1 = rb'((([\x00-\xff]{2})([\x00]{1}[\x37-\x82]{1})([\x01-\x80]{1})([\x01-\x80]{1})([\x00-\x09]{1})(([\x81-\xff]{1}[\x00-\x80]{1})|([\x19-\x80]{1})))((?=(.*\x74\x61\x62\x6C\x65))))'
regex_s2 = rb'((([\x00-\xff]{2})(([\x01-\x39]{1}[\x00-\xff]{1})|([\x40]{1}[\x00]{1})|([\x00]{1}[\x37-\xff]{1}))([\x17]{1})([\x01-\x80]{1})([\x01-\x80]{1})([\x00-\x09]{1})(([\x81-\xff]{1}[\x00-\x80]{1})|([\x19-\x80]{1})))((?=(.*\x74\x61\x62\x6C\x65))))'
regex_s3 = rb'((([\x00-\xff]{2})(([\x01-\x39]{1}[\x00-\xff]{1})|([\x40]{1}[\x00]{1})|([\x00]{1}[\x37-\xff]{1}))([\x06-\x0E]{1})([\x17]{1})([\x01-\x80]{1})([\x01-\x80]{1})([\x00-\x09]{1})(([\x81-\xff]{1}[\x00-\x80]{1})|([\x19-\x80]{1})))((?=(.*\x74\x61\x62\x6C\x65))))'

#List of simplified valid type, removing any condition (e.g. UNIQUE, ASC, DESC, PRIMARY KEY, FOREIGN KEY, etc.)
types_affinities = {'(INTEGER PRIMARY KEY)':'INTEGER PRIMARY KEY', '((INT)(?!.*NO.*NULL)(?!.*PRIMARY.*KEY))':'INTEGER', 
'((INT)(.*NO.*NULL))':'INTEGER NOT NULL', '(BOOL(?!.*NO.*NULL))':'BOOLEAN', '(BOOL.*NO.*NULL)':'BOOLEAN NOT NULL', 
'((CHAR|TEXT|CLOB)(?!.*NO.*NULL))':'TEXT', '((CHAR|TEXT|CLOB)(.*NO.*NULL))':'TEXT NOT NULL', '((BLOB|GUID|UUID)(?!.*NO.*NULL))':'BLOB', 
'((BLOB|GUID|UUID)(.*NO.*NULL))':'BLOB NOT NULL', '((REAL|DOUB|FLOA)(?!.*NO.*NULL))':'REAL', '((REAL|DOUB|FLOA)(.*NO.*NULL))':'REAL NOT NULL', 
'((NUMERIC|JSON)(?!.*NO.*NULL))':'NUMERIC', '((NUMERIC|JSON)(.*NO.*NULL))':'NUMERIC NOT NULL',
'((DATE)(?!.*NO.*NULL))':'DATETIME', '((DATE)(.*NO.*NULL))':'DATETIME NOT NULL'}

#After conversion of types, if there is still an unknown type (not on this list_types) left, replace it with "NUMERIC" or "NUMERIC NOT NULL"
list_types = ('INTEGER PRIMARY KEY', 'INTEGER', 'INTEGER NOT NULL', 'BOOLEAN', 'BOOLEAN NOT NULL', 'REAL', 'REAL NOT NULL', 
'TEXT', 'TEXT NOT NULL', 'NUMERIC', 'NUMERIC NOT NULL', 'DATETIME', 'DATETIME NOT NULL', 'BLOB', 'BLOB NOT NULL')




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




#Function that decodes bytes from potential true header into integers (so that we can do calculations on it afterwards) and appends them to unknown_header list
def decode_unknown_header(unknown_header, a, b, limit, len_start_header, freeblock=bool):
    
    #a & b are the beginning and the end of the match respectivly

    #Until end of the match
    count = 0
    
    #If the record is overwritten by a freeblock, read 2 bytes (next freeblock offset) then 2 bytes (length of this freeblock)
    if freeblock:
        byte = int(struct.unpack('>H', mm.read(2))[0])
        unknown_header.append(byte)
        count+=2
        
        byte = int(struct.unpack('>H', mm.read(2))[0])
        unknown_header.append(byte)
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
                count+=1
            
            #Else, handle Huffman encoding until 9 successive bytes
            else:
                cont1 = int(struct.unpack('>B', mm.read(1))[0])
                byte1 = int(huffmanEncoding(byte, cont1),16)
                if cont1 < 128:
                    unknown_header.append(byte1)
                    count+=2
                else:
                    cont2 = int(struct.unpack('>B', mm.read(1))[0])
                    byte2 = int(huffmanEncoding(byte1, cont2),16)
                    count+=2
                    if cont2 < 128:
                        unknown_header.append(byte2)
                        count+=1
                    else:
                        count+=1
                        cont3 = int(struct.unpack('>B', mm.read(1))[0])
                        byte3 = int(huffmanEncoding(byte2, cont3),16)
                        if cont3 < 128:
                            unknown_header.append(byte3)
                            count+=1
                        else:
                            count+=1
                            cont4 = int(struct.unpack('>B', mm.read(1))[0])
                            byte4 = int(huffmanEncoding(byte3, cont4),16)
                            if cont4 < 128:
                                unknown_header.append(byte4)
                                count+=1
                            else:
                                count+=1
                                cont5 = int(struct.unpack('>B', mm.read(1))[0])
                                byte5 = int(huffmanEncoding(byte4, cont5),16)
                                if cont5 < 128:
                                    unknown_header.append(byte5)
                                    count+=1
                                else:
                                    count+=1
                                    cont6 = int(struct.unpack('>B', mm.read(1))[0])
                                    byte6 = int(huffmanEncoding(byte5, cont6),16)
                                    if cont6 < 128:
                                        unknown_header.append(byte6)
                                        count+=1
                                    else:
                                        count+=1
                                        cont7 = int(struct.unpack('>B', mm.read(1))[0])
                                        byte7 = int(huffmanEncoding(byte6, cont7),16)
                                        if cont7 < 128:
                                            unknown_header.append(byte7)
                                            count+=1
                                        else:
                                            count+=1
                                            cont8 = int(struct.unpack('>B', mm.read(1))[0])
                                            byte8 = int(huffmanEncoding(byte7, cont8),16)
                                            if cont8 < 128:
                                                unknown_header.append(byte8)
                                                count+=1
                                            else:
                                                count+=1
                                                byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                unknown_header.append(byte9)
        
        
        #Serial types part : append(serialTypes(byte)) to unknown_header
        else:
            
            #Append limit to list of limits to know how many bytes takes the start of the header (because 3 integers are not necessarily only 3 bytes)
            limit.append(count)
            
            #Read byte by byte, convert in integer, and append to unknown_header list
            byte = int(struct.unpack('>B', mm.read(1))[0])
            
            #If byte < 0x80
            if byte < 128:
                unknown_header.append(serialTypes(byte))
                count+=1
            
            #Else, handle Huffman encoding until 9 successive bytes
            else:
                cont1 = int(struct.unpack('>B', mm.read(1))[0])
                byte1 = int(huffmanEncoding(byte, cont1),16)
                if cont1 < 128:
                    unknown_header.append(serialTypes(byte1))
                    count+=2
                else:
                    cont2 = int(struct.unpack('>B', mm.read(1))[0])
                    byte2 = int(huffmanEncoding(byte1, cont2),16)
                    count+=2
                    if cont2 < 128:
                        unknown_header.append(serialTypes(byte2))
                        count+=1
                    else:
                        count+=1
                        cont3 = int(struct.unpack('>B', mm.read(1))[0])
                        byte3 = int(huffmanEncoding(byte2, cont3),16)
                        if cont3 < 128:
                            unknown_header.append(serialTypes(byte3))
                            count+=1
                        else:
                            count+=1
                            cont4 = int(struct.unpack('>B', mm.read(1))[0])
                            byte4 = int(huffmanEncoding(byte3, cont4),16)
                            if cont4 < 128:
                                unknown_header.append(serialTypes(byte4))
                                count+=1
                            else:
                                count+=1
                                cont5 = int(struct.unpack('>B', mm.read(1))[0])
                                byte5 = int(huffmanEncoding(byte4, cont5),16)
                                if cont5 < 128:
                                    unknown_header.append(serialTypes(byte5))
                                    count+=1
                                else:
                                    count+=1
                                    cont6 = int(struct.unpack('>B', mm.read(1))[0])
                                    byte6 = int(huffmanEncoding(byte5, cont6),16)
                                    if cont6 < 128:
                                        unknown_header.append(serialTypes(byte6))
                                        count+=1
                                    else:
                                        count+=1
                                        cont7 = int(struct.unpack('>B', mm.read(1))[0])
                                        byte7 = int(huffmanEncoding(byte6, cont7),16)
                                        if cont7 < 128:
                                            unknown_header.append(serialTypes(byte7))
                                            count+=1
                                        else:
                                            count+=1
                                            cont8 = int(struct.unpack('>B', mm.read(1))[0])
                                            byte8 = int(huffmanEncoding(byte7, cont8),16)
                                            if cont8 < 128:
                                                unknown_header.append(serialTypes(byte8))
                                                count+=1
                                            else:
                                                count+=1
                                                byte9 = int(huffmanEncoding(byte7, cont8),16)
                                                unknown_header.append(serialTypes(byte9))

    return unknown_header, limit




#Function that creates the same table 3 times but without the last 1-2-3 columns, if --default True
def default_table(dictionary, name):
    for dictionaries in dictionary:
        for key2,value2 in dictionaries.items():
            list_values = list(value2.values())
            list_keys = list(value2.keys())

            #If last column contains a DEFAULT value and the table has more than 6 columns
            if 'DEFAULT' in list_values[-1] and ((len(list_values) > 6 and name == '_default_0]') or (len(list_values) > 5 and name == '_1]') or (len(list_values) > 4 and name == '_2]')):
                #Make a copy of the table
                default_dict = copy.deepcopy(dictionaries)
                #Pop out last column and rename table (cannot have twice same table name)
                for key,value in default_dict.items():
                    value.pop(list_keys[-1])
                    element = str(key[:-1]) + str(name)
                    keys_default[key] = element
                for key,value in default_dict.copy().items():
                    for key1,value1 in keys_default.items():
                        if key == key1:
                            default_dict[value1] = default_dict[key]
                            del default_dict[key]
                #Append new table to config.json
                config.append(default_dict)
            else:
                break



#Command-line arguments and options
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", nargs='+', help='Provide one, multiple or a directory of databases from which you want to extract the schema.')
parser.add_argument("-d", "--default", type=true_false, nargs='?', default=False, help='Create extra tables without the last 3 DEFAULT values. True or False, False by default.')
parser.add_argument("-o", "--output", nargs='?', help='Output to save config_database.json file(s).')
args = parser.parse_args()


#Retrieve argument user provided for --default
default = true_false(args.default)


#Retrieve input files (databases from which schema will be retrieved)

#List of --input files and their paths
db_files, db_paths = [], []

#For each database provided
for file_name in args.input:
    #If it's a directory
    if os.path.isdir(file_name):
        #Look for files inside
        for parent, dirnames, filenames in os.walk(file_name):
            for fn in filenames:
                #Retrieve database path
                filepath = os.path.join(parent, fn)
                #For each database in the directory
                if fn.endswith(".sqlite") or fn.endswith(".sqlite3") or fn.endswith(".db") or fn.endswith(".db3") or fn.endswith(".sqlitedb"):
                    #Append their name to db_files list and path to db_paths list
                    db_files.append(fn)
                    db_paths.append(filepath)
    #If it's file(s)
    elif os.path.isfile(file_name):
        #Append their name to db_files list
        db_files.append(file_name)
    #Else, nor file(s) nor directory
    else:
        print('\n\n', "Nor file(s) nor directory", '\n\n')



#tqdm for progress bar per file processment, its description is the database's name
pbar = tqdm(db_files)

#For each database provided as input
for db_file in pbar:
    
    #Refresh progress bar database's name
    pbar.set_description(db_file)
    
    #If a directory is given as input
    if os.path.isdir(args.input[0]):
        #The index of file being processed is the same for its path on db_paths list
        index = db_files.index(db_file)
        open_file = db_paths[index]
    #Else, no need for path
    else:
        open_file = db_file


    #Open database to retrieve general information and schema
    with open(open_file, 'r+b') as file:
        
        #Memory map database file and read from it
        mm = mmap.mmap(file.fileno(), length=0, access=mmap.ACCESS_READ)
        
        #Database size
        size = os.path.getsize(open_file)
        #Database name without extension
        file_name = Path(open_file).name
        file_name, extension = os.path.splitext(file_name)
        file_name = file_name.replace(extension, '')
        
        #Go to offset 0 of database
        mm.seek(0)

        #Read 16 bytes for the SQLite format 3 signature
        signature = mm.read(15)
        
        #If it's not an SQLite database
        if signature != b'\x53\x51\x4C\x69\x74\x65\x20\x66\x6F\x72\x6D\x61\x74\x20\x33':
            print('\n\n' + str(open_file) + " is not a sqlite 3 database" + '\n\n')
        
        #If it's an SQLite database
        else:
            mm.read(1)
            
            #Create a dictionary to store general information
            db_infos = {}
            
            #First information is the file name without the extension
            db_infos["file name"] = file_name
            
            #Then retrieve important header information

            #Page size
            page_size = int(struct.unpack('>H', mm.read(2))[0])
            db_infos["page size"] = str(page_size) + ' bytes'

            #Write version
            file_format_w = int(struct.unpack('>B', mm.read(1))[0])
            if file_format_w == 0:
                db_infos["write version"] = 'OFF'
            elif file_format_w == 1:
                db_infos["write version"] = 'Journal'
            elif file_format_w == 2:
                db_infos["write version"] = 'WAL'
            else:
                db_infos["write version"] = 'value problem'
          

            #Read version
            file_format_r = int(struct.unpack('>B', mm.read(1))[0])
            if file_format_w == 0:
                db_infos["read version"] = 'OFF'
            elif file_format_w == 1:
                db_infos["read version"] = 'Journal'
            elif file_format_w == 2:
                db_infos["read version"] = 'WAL'
            else:
                db_infos["read version"] = 'value problem'
            
            #Reserved bytes
            reserved_bytes = int(struct.unpack('>B', mm.read(1))[0])
            db_infos["reserved bytes"] = str(reserved_bytes) + ' bytes'

            mm.read(3)
            
            #Database updates
            file_change_counter = int(struct.unpack('>i', mm.read(4))[0])
            db_infos["database updates"] = str(file_change_counter)

            #Number of pages
            number_pages = int(struct.unpack('>i', mm.read(4))[0])
            db_infos["number of pages"] = str(number_pages)

            #Database size
            db_size = int(page_size) * int(number_pages)
            db_infos["database size"] = str(db_size) + ' bytes'

            mm.read(8)

            #Schema changes
            schema_cookie = int(struct.unpack('>i', mm.read(4))[0]) 
            db_infos["schema changes"] = str(schema_cookie)

            mm.read(8)

            #Auto-vacuum parameter
            auto_vacuum = int(struct.unpack('>i', mm.read(4))[0]) 
            if auto_vacuum == 0:
                db_infos["auto-vacuum"] = 'OFF'
            else:
                db_infos["auto-vacuum"] = 'ON'

            #Text encoding
            text_encoding = int(struct.unpack('>i', mm.read(4))[0])
            if text_encoding == 1:
                db_infos["text encoding"] = 'UTF-8'
            elif text_encoding == 2:
                db_infos["text encoding"] = 'UTF-16le'
            elif text_encoding == 3:
                db_infos["text encoding"] = 'UTF-16be'
            else:
                db_infos["text encoding"] = 'value problem'


            mm.read(36)

            #SQLite version
            sqlite_version = int(struct.unpack('>i', mm.read(4))[0])
            a = round(sqlite_version/1000000)
            b = round((sqlite_version-(a*1000000))/1000)
            c = sqlite_version-(a*1000000)-(b*1000)
            db_infos["sqlite version"] = str(a) + '.' + str(b) + '.' + str(c)

            #Config.json file is an array of dicts
            config = []
            
            #Append dictionary of general database information to config array
            config.append(db_infos)



            #Compile each CREATE TABLE statement regex
            regex_s0 = re.compile(regex_s0)
            regex_s1 = re.compile(regex_s1)
            regex_s2 = re.compile(regex_s2)
            regex_s3 = re.compile(regex_s3)
            
            
            #List of CREATE TABLE statements
            payloads = []

            #SCENARIO 0 : non-overwritten statements
            #List of matches of regex
            matches = [match for match in re.finditer(regex_s0, mm, overlapped=True)]
            
            #For each match
            for match in matches:
                unknown_header, limit, payload = [], [], []
                a = match.start()
                b = match.end()

                #Go to start of the match
                mm.seek(a)

                #Decode unknown header : bytes --> integers
                decode_unknown_header(unknown_header, a, b, limit, len_start_header=3, freeblock=False)

                #If the payload length is equal to the sum of each type length plus the length of the serial types array
                #AND the serial types array length is equal to the number of bytes from the serial types array length
                if ((unknown_header[0] == sum(unknown_header[2:])) and (b-a-limit[0]+1 == unknown_header[2])):
                    
                     #Go to the end of the match to start reading payload content that comes just after the header/match
                    mm.seek(b)

                    #For each field's length of the record
                    for l in ((unknown_header)[3:]):
                        #Read bytes for that length and decode it according to encoding
                        payload_field = mm.read(l).decode('utf-8', errors='ignore')
                        #Append the content to payload list
                        payload.append(payload_field)
                    #Append the payload to payloads list
                    payloads.append(payload)
            


            #Overwritten statements according to 3 scenarios

            #SCENARIO 1
            matches_s1 = [match_s1 for match_s1 in re.finditer(regex_s1, mm, overlapped=True)]
            for match_s1 in matches_s1:
                unknown_header_s1, limit_s1, payload_s1 = [], [], []
                a = match_s1.start()
                b = match_s1.end()

                mm.seek(a)

                decode_unknown_header(unknown_header_s1, a, b, limit_s1, len_start_header=2, freeblock=True)
    
                #If the freeblock length is equal to the sum of each type length plus the length of the serial types array
                if (unknown_header_s1[1] == ((sum(unknown_header_s1[2:]))+5+(b-a))):
                    #As we lost type1, and we know it's always 'table', we can add the integer '5' as type1 in unknown_header
                    unknown_header_s1.insert(2, 5)
                    
                    mm.seek(b)

                    for l in ((unknown_header_s1)[2:]):
                        payload_field_s1 = mm.read(l).decode('utf-8', errors='ignore')
                        payload_s1.append(payload_field_s1)
                    
                    for element in payloads:
                        #If table not already in payloads, append table
                        if element[1] != payload_s1[1]:
                            payloads.append(payload_s1)

                    #If table was added in payloads and it's a correct CREATE TABLE statement
                    if (payload_s1 in payloads) and (str(payload_s1[1]) != '') and ('index' not in payload_s1[0]) and ('CREATE I' not in payload_s1[-1]) and ((payload_s1[-1])[0:12] == 'CREATE TABLE'):
                        #Then notify the user that a deleted table was retrieved (records will be retrieved normally)
                        print('\n\n\n', 'Overwritten table', str('"'+payload_s1[1]+'"'), 'was successfully retrieved!', '\n\n')



            #SCENARIO 2
            matches_s2 = [match_s2 for match_s2 in re.finditer(regex_s2, mm, overlapped=True)]
            for match_s2 in matches_s2:
                unknown_header_s2, limit_s2, payload_s2 = [], [], []
                a = match_s2.start()
                b = match_s2.end()

                mm.seek(a)

                decode_unknown_header(unknown_header_s2, a, b, limit_s2, len_start_header=2, freeblock=True)
    
                #If the freeblock length is equal to the sum of each type length plus the length of the serial types array
                if (unknown_header_s2[1] == ((sum(unknown_header_s2[2:]))+(b-a))):

                    mm.seek(b)
                    
                    for l in ((unknown_header_s2)[2:]):
                        payload_field_s2 = mm.read(l).decode('utf-8', errors='ignore')
                        payload_s2.append(payload_field_s2)
                    for element in payloads:
                        if element[1] != payload_s2[1]:
                            payloads.append(payload_s2)
                    if (payload_s2 in payloads) and (str(payload_s2[1]) != '') and ('index' not in payload_s2[0]) and ('CREATE I' not in payload_s2[-1]) and ((payload_s2[-1])[0:12] == 'CREATE TABLE'):
                        print('\n\n\n', 'Overwritten table', str('"'+payload_s2[1]+'"'), 'was successfully retrieved!', '\n\n')
            


            #SCENARIO 3
            matches_s3 = [match_s3 for match_s3 in re.finditer(regex_s3, mm, overlapped=True)]
            for match_s3 in matches_s3:
                unknown_header_s3, limit_s3, payload_s3 = [], [], []
                a = match_s3.start()
                b = match_s3.end()

                mm.seek(a)

                decode_unknown_header(unknown_header_s3, a, b, limit_s3, len_start_header=3, freeblock=True)
    
                #If the freeblock length is equal to the sum of each type length plus the length of the serial types array
                if ((sum(unknown_header_s3[2:]) + 4) == (unknown_header_s3[1])):
                   
                    mm.seek(b)
                    
                    for l in ((unknown_header_s3)[4:]):
                        payload_field_s3 = mm.read(l).decode('utf-8', errors='ignore')
                        payload_s3.append(payload_field_s3)
                    for element in payloads:
                        if element[1] != payload_s3[1]:
                            payloads.append(payload_s3)
                    if (payload_s3 in payloads) and  (str(payload_s3[1]) != '') and ('index' not in payload_s3[0]) and ('CREATE I' not in payload_s3[-1]) and ((payload_s3[-1])[0:12] == 'CREATE TABLE'):
                        print('\n\n\n', 'Overwritten table', str('"'+payload_s3[1]+'"'), 'was successfully retrieved!', '\n\n')



            #Free the memory
            mm.close()
            
            
            #For each statement
            for payload in payloads:
                #Verify that it is a CREATE TABLE table statement, and that it has no sqlite reserved table name (starting with 'sqlite_')
                if (payload[0] == 'table') and ('CREATE TABLE' or 'create table' in payload[4]) and not ('_Sqlite' in payload[1]) and not ('sqlite_' in payload[1]) and not ('SQLITE_' in payload[1]):
                    #Keep on completing config.json with table/fields information
                    table_name = payload[1]

                    #Handle table's names containing special characters
                    for i in table_name:
                        if ord(i) <= 20:
                            table_name = table_name.replace(i, 'character_before_20')
                    
                    if payload[1] == '(':
                        fields = payload[4].split('(',2)[2]
                    else:
                        try:
                            fields = payload[4].split('(',1)[1]
                        except:
                            pass
                    
                    if type(table_name) == int:
                        table_name = 'special_character_' + str(table_name)

                    #Clean table's name
                    if table_name == "''":
                        table_name = '\'\''
                    if table_name == '""':
                        table_name = '\"\"'
                    table_name = table_name.replace("'", "apostrophe_exception_name")
                    table_name = table_name.replace('"', "quotation_exception_name")
                    table_name = table_name.replace('--', "double_dash_exception_name")
                    table_name = table_name.replace('[', "bracket_exception_name")
                    table_name = table_name.replace(']', "bracket_exception_name")
                    table_name = table_name.replace('%s', "parameterized_string_exception_name")

                    #Sanitize table name with [ ] to avoid internal names errors
                    if (not table_name.startswith('[')) and (not table_name.endswith(']')):
                        table_name = ''.join(['[', table_name ,']'])

                    #Escape unicode in tables' names
                    re_pattern = r'[^\\u0000-\u007F]'
                    if len(table_name) > 3:
                        table_name = re.sub(re_pattern, '', table_name)

                    #Make sure fields is a tuple
                    if type(fields) == list:
                        fields = ' '.join(fields)
                    
                    #Clean columns' fields
                    if fields.endswith(' )'):
                        fields = fields[:-2]
                    if fields.endswith(')'):
                        fields = fields[:-1]
                    if fields.endswith(','):
                        fields = fields[:-1]
                    
                    #Clean end-statement conditions
                    fields = re.sub(r'(PRIMARY KEY){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(,PRIMARY KEY){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(, PRIMARY KEY){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(FOREIGN KEY){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(,FOREIGN KEY){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(, FOREIGN KEY){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(UNIQUE){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(DISTINCT){1}( )*\({1}.+\)', '', fields)
                    fields = re.sub(r'(CHECK){1}( )*\({1}.+', '', fields)
                    fields = re.sub(r'(COLLATE ){1}', '', fields)
                    fields = re.sub(r'(ASC ){1}', '', fields)
                    fields = re.sub(r'(DESC ){1}', '', fields)
                    fields = re.sub(r'(REFERENCES ){1}', '', fields)
                    fields = re.sub(r'(CONSTRAINT ){1}', '', fields)
                    fields = re.sub(r'(DECIMAL(.*)){1}', '', fields)
                    fields = re.sub(r'(NUMERIC(.*)){1}', '', fields)
                    fields = re.sub(r'(ON (DELETE|UPDATE) ((SET (NULL|DEFAULT))|CASCADE|RESTRICT|NO ACTION)){1}', '', fields)
                    fields = re.sub(r'(ON CONFLICT (ROLLBACK|ABORT|FAIL|IGNORE|REPLACE){1})', '', fields)
                    fields = re.sub(r'((GENERATED( ALWAYS {0,1}) AS){1}( )*\({1}.+\)( STORED|VIRTUAL){0,1})', '', fields)
                    fields = re.sub(r'(FILTER{1}( )*\({1}.+\))', '', fields)
                    fields = re.sub(r'(RAISE{1}( )*\({1}.+\))', '', fields)
                    fields = re.sub(r'(INTEGER{1}( )*\({1}.+\))', 'INTEGER', fields)
                    

                    #Fields are separated by commas in a CREATE TABLE statement
                    fields = fields.split(',')

                    #Put table name and each associated field in same list
                    field_list_config = []
                    
                    #For each separated by comma field
                    for i in fields:
                        
                        #Need cleaning again
                        if i.startswith('\n\t'):
                            i = i[1:]
                        if i.startswith('\n\\'):
                            i = i[2:]
                        if i.startswith(' '):
                            i = i[1:]
                        i = i.replace('\t', ' ')
                        i = i.replace('\r', ' ')
                        i = i.replace('\n', '')
                        i = i.replace('\\', '')
                        if i.startswith(' "'):
                            i = i[2:]
                        while i.startswith(' '):
                            i = i[1:]

                        #Separate column's name and type by first space (if column name has a space, we will lose the second part)
                        _name_ = i.partition(' ')
                        
                        #Exception if the name was a space or started by a space
                        if _name_[0] == '':
                            _name_ = i.partition(' ')

                        
                        #Name is before space, type is after space
                        name_ = _name_[0]
                        
                        #Escape unicode in names
                        name_ = re.sub(re_pattern, '', name_)
                        
                        #Sanitize column name with [ ] to avoid internal names errors
                        if (not name_.startswith('[')) and (not name_.endswith(']')):
                            name_ = ''.join(['[', name_ ,']'])
                        
                        type_ = _name_[2]

                        #Clean name                        
                        if name_.startswith("'") and name_.endswith("'"):
                            name_ = name_[1:-1]
                        if name_.startswith('"') and name_.endswith('"'):
                            name_ = name_[1:-1]
                        if name_.endswith(' "'):
                            name_ = name_[:-2]
                        if (name_.endswith('"') and (not name_.startswith('"'))):
                            name_ = name_[:-1]
                        if (name_.startswith('"') and (not name_.endswith('"'))):
                            name_ = name_[1:]
                        if (name_.endswith(']') and (not name_.startswith('['))):
                            name_ = name_[:-1]
                        if (name_.startswith('[') and (not name_.endswith(']'))):
                            name_ = name_[1:]

                        #If empty or non-relevant name and type
                        if (name_ == '[]') or (name_ == '' and type_ == '') or (name_ == "\n" and type_ == "") or (name_ == "" and type_ == " ") or (name_ == "" and type_ == "  "):
                            pass
                        
                        #Else, it's relevant name and type
                        else:
                            #If there is a column name but type is empty, type = numeric
                            if type_ == '':
                                type_ = 'NUMERIC'
                            
                            #Replace each column type with a simplified valid type in types_affinities, removing any condition (e.g. UNIQUE, ASC, DESC, etc.)
                            for key,value in types_affinities.items():
                                if 'DEFAULT' not in type_:
                                    type_ = re.sub(rf'.*{key}.*', value, type_, flags=re.IGNORECASE)
                                #If type contains a DEFAULT condition, keep it as DEFAULT 0
                                else:
                                    type_ = re.sub(rf'.*{key}.*', value + ' DEFAULT 0', type_, flags=re.IGNORECASE)

                            #If there is still an unknown type (not on list_types) left, replace it with "NUMERIC" or "NUMERIC NOT NULL"
                            if type_ not in list_types and 'DEFAULT' not in type_:
                                if 'NOT NULL' in type_:
                                    type_ = 'NUMERIC NOT NULL'
                                else:
                                    type_ = 'NUMERIC'

                            #Append name and type dicts elements to field_list_config list
                            field_list_config.append(name_)
                            field_list_config.append(type_)
                    

                    #If command-line argument --default True
                    if default:
                        #For tables with > 6 columns, add DEFAULT NULL at the 3 last columns if they don't already contain a DEFAULT or a NOT NULL condition
                        #This is to handle old versions of tables that just added columns afterwards in newer versions but old records still have less columns and take the default value for the additionnal ones...
                        if len(field_list_config) >= 12 :
                            if 'DEFAULT' not in field_list_config[-1]:
                                if 'NOT NULL' not in field_list_config[-1]:
                                    field_list_config[-1] += ' DEFAULT NULL'
                                else:
                                    field_list_config[-1] += ' DEFAULT 0'
                            if 'DEFAULT' not in field_list_config[-3]:
                                if 'NOT NULL' not in field_list_config[-3]:
                                    field_list_config[-3] += ' DEFAULT NULL'
                                else:
                                    field_list_config[-3] += ' DEFAULT 0'
                            if 'DEFAULT' not in field_list_config[-5]:
                                if 'NOT NULL' not in field_list_config[-5]:
                                    field_list_config[-5] += ' DEFAULT NULL'
                                else:
                                    field_list_config[-5] += ' DEFAULT 0'


                    #Remove NOT NULL from first column because it will necessarily be a 0 for rowid tables!
                    try:
                        if 'NOT NULL' in field_list_config[1]:
                            field_list_config[1] = field_list_config[1].replace('NOT NULL', '')
                    except IndexError:
                        pass


                    #Make a dictionary per table with a list of columns' names and fields
                    dict_transf_config = {field_list_config[i]: field_list_config[i + 1] for i in range(0, len(field_list_config), 2)}
                    fields_lists_config = {table_name:dict_transf_config}
                    
                    #Append dictionary to config array
                    if fields_lists_config not in config:
                        config.append(fields_lists_config)
                    
                    #Sort config.json dicts by table name
                    config[1:] = sorted(config[1:], key=lambda d: list(d.keys()))


            #Make a copy of a table if two tables share the same name in the schema : table_name + '_copy' (until max 5 copies)
            keys_copies = {}

            for i in range(5):
                for a,b in itertools.combinations(config[1:],2):
                    if a.keys() == b.keys():
                        for key,value in b.items():
                            element = '[' + str(key[1:-1]) + '_copy]'
                            keys_copies[key] = element
                for a,b in itertools.combinations(config[1:],2):
                    if a.keys() == b.keys():
                        for key,value in keys_copies.items():
                            for key1,value1 in b.copy().items():
                                if key == key1:
                                    b[value] = b[key1]
                                    del b[key]
        

        
            #If command-line argument --default True
            if default:
                #Default case : take out one by one 3 last default for tables that have more than 6 columns and create new tables, potential old versions
                #E.g. table name = sms, we will have table sms, table sms_default_0 without last column of sms, 
                #table sms_default_0_1 without last column of sms_default_0, table sms_default_0_1_2 without last column of sms_default_0_1
                keys_default = {}
                name = '_default_0]'
                z = 1
                x = len(config)
                default_table(config[z:], name)
                name = '_1]'
                y = len(config)
                if y == x:
                    pass
                default_table(config[x:], name)
                name = '_2]'
                w = len(config)
                if w == y:
                    pass
                default_table(config[y:], name)
                v = len(config)
                if v == w:
                    pass

        
            #Create config_databasename.json
            output_config = "config_%s.json" % file_name

            #If user didn't complete output path with final /
            if not args.output.endswith("/"):
                args.output += "/"
            
            #Write config array in the json file
            with open (args.output + output_config, 'w') as config_file:
                json.dump(config, config_file, indent=2)
            
            #Close json file
            config_file.close()
        
        #Free the memory
        mm.close
    
    #Close database file
    file.close()
