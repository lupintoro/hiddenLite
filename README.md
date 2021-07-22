# hiddenLite
 
**1) Create config.json file(s):**

        ````bash
        config.py --input /path/to/database_file(s)_OR_directory_of_files --default True/False (False by default) --output /path/to/output/folder
        ````

--input: provide database(s) to retrieve its/their schema (if directory, can contain all sort of files, not only databases)

--default: create extra tables without last 1,2,3 columns in case of table update (e.g. application update, table has more columns, old records keep their old structure)

--output: path to store config.json file(s)

--> Possible to correct schema errors in the config.json file before running sqlite_parser.py or to remove tables that are not of interest



Examples:

    config.py --input directory --default False --output ./

    config.py --input mmssms.db --default True --output ./

    config.py --input mmssms.db snap.db --default False --output ./





**2) Write records to output database(s):**

        ````bash
        sqlite_parser.py --config /path/to/config_file(s)_OR_directory_of_files --input /path/to/database_file(s)_OR_directory_of_files --linked True/False (True by default) --single_column True/False (False by default) --keyword example (not required) --output /path/to/output/folder
        ````

--config: provide every config.json file or a directory of config.json files that was/were created at step 1)

--input: provide all file(s) or directory of interest to parse 
(e.g. WAL/journal files, many databases with same schema, a directory with files that have the same schema or with any sort of files)

--linked: parse only files that are linked to the database used to create config.json file (True) or all sort of files (False)

--single_column: parse overwritten records from 1-column tables (True) or not (False) 
(if True, slows down parsing. Non-overwritten records (scenario 0) from 1-column tables are still parserd)

--keyword: only parses records containing the keyword 
(case sensitive keyword searching, e.g. http)

--output: path to store output.db file(s)



Examples:
    
    sqlite_parser.py --config config_mmssms.db --input mmssms.db --single_column True --keyword SMS --output ./
    (here input file is already linked to initial database)
    
    sqlite_parser.py --config config_mmssms.db --input mmssms.db mmssms.db-journal mmssms.db-wal --keyword sms --output ./
    (here input files are already linked to initial database)

    sqlite_parser.py --config config_mmssms.db config_snap.db --input directory --linked False --output ./
    (here parsing will be done in all files in the directory)

    sqlite_parser.py --config directory1 --input directory2 --output ./
    (directory1 contains config.json files of interest --> can contain other files)
    (directory2 contains files linked with the initial database)