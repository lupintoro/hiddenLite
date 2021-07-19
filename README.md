# hiddenLite
 
**1) Create config.json file(s):**

        ````bash
        config.py --input /path/to/database_file(s)_OR_directory_of_files --default True/False (default False) --output /path/to/output/folder
        ````

--> Provide database(s) to retrieve its/their schema

--> Directory can contain all sort of files

--> Possible to correct schema errors in config.json file before running sqlite_parser.py


Examples:

    config.py --input directory --default False --output ./

    config.py --input mmssms.db --default False --output ./

    config.py --input mmssms.db snap.db --default False --output ./



**2) Write records to output database(s):**

        ````bash
        sqlite_parser.py --config /path/to/config_file(s)_OR_directory_of_files --input /path/to/database_file(s)_OR_directory_of_files --keyword [not required] --output /path/to/output/folder
        ````

--> Provide every config.json file that was created at step 1)

--> Provide all file or directory of interest, e.g. WAL/journal/slack files, many databases with same schema, a directory with files of interest that have the same schema as in the config.json files


Examples:
    
    sqlite_parser.py --config config_mmssms.db --input mmssms.db --keyword SMS --output ./
    
    sqlite_parser.py --config config_mmssms.db --input mmssms.db mmssms.db-journal mmssms.db-journal-slack mmssms.db-wal --output ./

    sqlite_parser.py --config config_mmssms.db config_snap.db --input directory --output ./
    --> directory that contains for example db/journal/WAL/slack files associated with mmssms.db and for snap.db

    sqlite_parser.py --config directory1 --input directory2 --output ./
    --> directory1 that contains the config.json files of interest --> can contain other files 
    --> directory2 that contains for example db/journal/WAL/slack files associated with databases used to create the config.json files provided in directory1