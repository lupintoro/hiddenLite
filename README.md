# hiddenLite

HiddenLite parses a file and retrieves all matches found with regular expressions of SQLite records. It can thus recover current database records, but also deleted or unreferenced records. This tool parses SQLite databases, but also journal/WAL files, binary images or any other file provided to it.


##########      config.py     ##########

This script retrieves table schemas from a database file given as argument and writes the database's and schema's information to a config_database.json file.


##########      sqlite_parser.py     ##########

This script takes config_database.json and a file to parse as arguments. It then scans the latter for matches with regular expressions of records, generated according to the schema provided by config_database.json. The retrieved records are written to an output_database.db of same schema as the one retrieved by config.py.


 
**1) Create config.json file(s):**

        ````bash
        config.py [-i input_file(s)_or_directory_path] [-d True/False (default False)] [-o output.json_path]
        ````

-i: provide database(s) to retrieve its/their schema (if directory, can contain all sort of files, not only databases)

-d: create extra tables without last 1,2,3 columns in case of different record structure per table 
(e.g. application update --> table has more columns but old records keep their old structure)

-o: path to store config.json file(s)


--> Possible to correct schema errors in the config.json file before running sqlite_parser.py or to remove tables that are not of interest



Examples:

    config.py -i directory -d False -o ./

    config.py -i mmssms.db -d True -o ./

    config.py -i mmssms.db snap.db history.db -d False - ./





**2) Write records to output database(s):**

        ````bash
        sqlite_parser.py [-c config_file(s)_or_directory_path] [-i database_file(s)_or_directory_path] [-l True/False (default True)] [-k keyword (not required)] [-o output.db_path]
        ````

-c: provide every config.json file or a directory of config.json files that was/were created at step 1)

-i: provide all file(s) or directory of interest to parse 
(e.g. WAL/journal files, many databases with same schema, a directory with any sort of files)

-l: parse only files that are linked to the database used to create config.json file (True) or all files provided (False)

-k: only parses records containing the keyword 
(case sensitive keyword searching, e.g. http)

-o: path to store output.db file(s)



Examples:


    sqlite_parser.py -c config_mmssms.json -i mmssms.db -k SMS -o ./
    
    (here input file is already linked to initial database)
    (here only records with keyword "SMS" will be parsed)
    


    sqlite_parser.py -c config_mmssms.json -i mmssms.db mmssms.db-journal mmssms.db-wal -k sms -o ./
    
    (here input files are already linked to initial database)


    
    sqlite_parser.py -c config_history.json -i history.db -k http -o ./
    
    (here only records with keyword "http" will be parsed)


    
    sqlite_parser.py -c config_history.json -i samsung.bin -l False -o ./
    
    (here we give a binary image of a mobile device in which we want to search for browser history records)
    (the linked -l argument must be False because it's not a file directly linked to history.db)

    

    sqlite_parser.py -c config_mmssms.json config_snap.json -i directory -l False -o ./
    
    (here parsing will be done for all files in the directory (-l False))


    
    sqlite_parser.py -c directory1 -i directory2 -o ./
    
    (directory1 contains config.json files of interest (can contain other files))
    (directory2 contains files linked (-l default True) with initial databases used to create config.json files)