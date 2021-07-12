# hiddenLite
 
**1) Create config.json file(s):**

        ````bash
        config.py --filename /path/to/database_file(s)_OR_directory_of_files
        ````

--> Provide database(s) to retrieve its/their schema

--> Directory can contain all sort of files

--> Possible to correct schema errors in config.json file


Examples:

    config.py --filename directory

    config.py --filename mmssms.db

    config.py --filename mmssms.db snap.db 



**2) Write records to output database(s):**

        ````bash
        sqlite_parser.py --config /path/to/every/config/file --main_file /path/to/database_file(s)_OR_directory_of_files
        ````

--> Provide every config.json file that was created at step 1)

--> Provide all file or directory of interest, e.g. WAL/journal/slack files, many databases with same schema, a directory with files of interest that have the same schema as in the config.json files


Examples:
    
    sqlite_parser.py --config config_mmssms.db --main_file mmssms.db
    
    sqlite_parser.py --config config_mmssms.db --main_file mmssms.db mmssms.db-journal mmssms.db-journal-slack mmssms.db-wal
    
    sqlite_parser.py --config config_mmssms.db config_snap.db --main_file directory
    (here a directory that contains for example journal/WAL/slack files for mmssms.db and for snap.db)

