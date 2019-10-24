import os
import cx_Oracle
import sys
import eneel.utils as utils
from concurrent.futures import ThreadPoolExecutor as Executor

import logging
logger = logging.getLogger('main_logger')


def run_export_cmd(cmd_commands):
    envs = [['NLS_LANG', 'SWEDISH_SWEDEN.WE8ISO8859P1']]
    cmd_code, cmd_message = utils.run_cmd(cmd_commands, envs)
    if cmd_code == 0:
        logger.debug(cmd_commands[2] + " exported")
        return 0
    else:
        logger.error(
            "Error exportng " + cmd_commands[2] + " : cmd_code: " + str(cmd_code) + " cmd_message: " + cmd_message)
        return 0

def run_export_query(server, user, password, database, port, query, file_path, delimiter, rows=5000):
    print('loading')
    try:
        db = Database(server, user, password, database, port)
        export = db.cursor.execute(query)
        rowcounts = 0
        while rows:
            try:
                rows = export.fetchmany(rows)
            except:
                return rowcounts
            rowcount = utils.export_csv(rows, file_path, delimiter)  # Method appends the rows in a file
            rowcounts = rowcounts + rowcount
    except Exception as e:
        logger.error(e)


class Database:
    def __init__(self, server, user, password, database, port=None, limit_rows=None, table_where_clause=None, read_only=False,
                 table_parallel_loads=10, table_parallel_batch_size=1000000):
        try:
            server_db = '{}:{}/{}'.format(server, port, database)
            self._server = server
            self._user = user
            self._password = password
            self._database = database
            self._port = port
            self._server_db = server_db
            self._dialect = "oracle"
            self._limit_rows = limit_rows
            self._table_where_clause = table_where_clause
            self._read_only = read_only
            self._table_parallel_loads = table_parallel_loads
            self._table_parallel_batch_size = table_parallel_batch_size

            self._conn = cx_Oracle.connect(user, password, server_db)
            self._cursor = self._conn.cursor()
            logger.debug("Connection to oracle successful")
        except cx_Oracle.Error as e:
            logger.error(e)
            sys.exit(1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()
        self._conn.close()

    def close(self):
        self._conn.close()

    @property
    def connection(self):
        return self._conn

    @property
    def cursor(self):
        return self._cursor

    def commit(self):
        self.connection.commit()

    def execute(self, sql, params=None):
        try:
            return self.cursor.execute(sql, params or ())
        except cx_Oracle.Error as e:
            logger.error(e)

    def execute_many(self, sql, values):
        try:
            return self.cursor.executemany(sql, values)
        except cx_Oracle.Error as e:
            logger.error(e)

    def fetchall(self):
        try:
            return self.cursor.fetchall()
        except cx_Oracle.Error as e:
            logger.error(e)

    def fetchone(self):
        try:
            return self.cursor.fetchone()
        except cx_Oracle.Error as e:
            logger.error(e)

    def fetchmany(self,rows):
        try:
            return self.cursor.fetchmany(rows)
        except cx_Oracle.Error as e:
            logger.error(e)

    def query(self, sql, params=None):
        try:
            self.cursor.execute(sql, params or ())
            return self.fetchall()
        except cx_Oracle.Error as e:
            logger.error(e)

    def schemas(self):
        try:
            q = 'SELECT DISTINCT OWNER FROM ALL_TABLES'
            schemas = self.query(q)
            return schemas
        except:
            logger.error("Failed getting schemas")

    def tables(self):
        try:
            q = "select OWNER || '.' || TABLE_NAME from ALL_TABLES"
            tables = self.query(q)
            return tables
        except:
            logger.error("Failed getting tables")

    def table_columns(self, schema, table):
        try:
            q = """
                SELECT 
                      COLUMN_ID AS ordinal_position,
                      COLUMN_NAME AS column_name,
                      DATA_TYPE AS data_type,
                      DATA_LENGTH AS character_maximum_length,
                      DATA_PRECISION AS numeric_precision,
                      DATA_SCALE AS numeric_scale
                FROM all_tab_cols
                WHERE 
                    owner = :s
                    and table_name = :t
                    AND COLUMN_ID IS NOT NULL
                    order by COLUMN_ID
                    """
            columns = self.query(q, [schema, table])
            return columns
        except:
            logger.error("Failed getting columns")

    def check_table_exist(self, table_name):
        try:
            check_statement = """
            SELECT 1
           FROM   ALL_TABLES 
           WHERE  OWNER || '.' || TABLE_NAME = '""" + table_name + "'"
            exists = self.query(check_statement)
            if exists:
                return True
            else:
                return False
        except:
            logger.error("Failed checking table exist")

    def truncate_table(self, table_name):
        return 'Not implemented for this adapter'

    def create_schema(self, schema):
        return 'Not implemented for this adapter'

    def get_max_column_value(self, table_name, column):
        return 'Not implemented for this adapter'

    def get_min_max_column_value(self, table_name, column):
        try:
            sql = "SELECT MIN(" + column + "), MAX(" + column + ") FROM " + table_name
            res = self.query(sql)
            min_value = int(res[0][0])
            max_value = int(res[0][1])
            return min_value, max_value
        except:
            logger.debug("Failed getting min and max column value")

    def get_min_max_batch(self, table_name, column):
        try:
            sql = "SELECT MIN(" + column + "), MAX(" + column
            sql += "), ceil((max( " + column + ") - min("
            sql += column + ")) / (count(*)/" + str(self._table_parallel_batch_size) + ".0)) FROM " + table_name
            res = self.query(sql)
            print(sql)
            min_value = int(res[0][0])
            max_value = int(res[0][1])
            batch_size_key = int(res[0][2])
            return min_value, max_value, batch_size_key
        except:
            logger.debug("Failed getting min, max and batch column value")

    def generate_cmd_file(self, sql_file):
        cmd = "export NLS_LANG=SWEDISH_SWEDEN.WE8ISO8859P1\n"
        #cmd += "set NLS_NUMERIC_CHARACTERS=. \n"
        #cmd += "set NLS_TIMESTAMP_TZ_FORMAT=YYYY-MM-DD HH24:MI:SS.FF\n"
        cmd += "sqlplus " + self._user + "/" + self._password + "@//" + self._server_db + " @" + sql_file
        logger.debug(cmd)
        return cmd

    def generate_cmd_command(self, sql_file):
        cmd = 'sqlplus'
        ora_conn = self._user + "/" + self._password + "@//" + self._server_db
        sqlfile = '@' + sql_file
        cmd_to_run = [cmd, ora_conn, sqlfile]
        return cmd_to_run

    def generate_spool_cmd(self, file_path, select_stmt):
        spool_cmd = """
alter session set NLS_NUMERIC_CHARACTERS = '. ';
alter session set NLS_TIMESTAMP_TZ_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF';
set markup csv on quote off
set term off
set echo off
set trimspool on 
set trimout on
set feedback off
Set serveroutput off
set heading off
set arraysize 5000
SET LONG 32767 
spool """

        spool_cmd += file_path + '\n'
        spool_cmd += select_stmt
        spool_cmd += "spool off\n"
        spool_cmd += "exit"
        logger.debug(spool_cmd)
        return spool_cmd

    def generate_spool_query(self, columns, delimiter, schema, table, replication_key=None, max_replication_key=None, parallelization_where=None):
        # Generate SQL statement for extract
        select_stmt = "SELECT "
        for col in columns[:-1]:
            column_name = col[1]
            select_stmt += "REPLACE(" + column_name + ",chr(0),'')" + " || '" + delimiter + "' || \n"
        last_column_name = "REPLACE(" + columns[-1:][0][1] + ",chr(0),'')"
        select_stmt += last_column_name
        select_stmt += ' FROM ' + schema + "." + table

        # Where-claues for incremental replication
        if replication_key:
            replication_where = replication_key + " > " + "'" + max_replication_key + "'"
        else:
            replication_where = None

        wheres = replication_where, self._table_where_clause, parallelization_where
        wheres = [x for x in wheres if x is not None]
        if len(wheres) > 0:
            select_stmt += " WHERE " + wheres[0]
            for where in wheres[1:]:
                select_stmt += " AND " + where

        if self._limit_rows:
            select_stmt += " FETCH FIRST " + str(self._limit_rows) + " ROW ONLY"

        select_stmt += ";\n"

        return select_stmt

    def generate_export_query(self, columns, schema, table, replication_key=None, max_replication_key=None,
                              parallelization_where=None):
        # Generate SQL statement for extract
        select_stmt = "SELECT "
        # Add columns
        for col in columns:
            column_name = col[1]
            select_stmt += column_name + ", "
        select_stmt = select_stmt[:-2]

        select_stmt += ' FROM ' + schema + "." + table

        # Where-claues for incremental replication
        if replication_key:
            replication_where = replication_key + " > " + "'" + max_replication_key + "'"
        else:
            replication_where = None

        wheres = replication_where, self._table_where_clause, parallelization_where
        wheres = [x for x in wheres if x is not None]
        if len(wheres) > 0:
            select_stmt += " WHERE " + wheres[0]
            for where in wheres[1:]:
                select_stmt += " AND " + where

        if self._limit_rows:
            select_stmt += " FETCH FIRST " + str(self._limit_rows) + " ROW ONLY"

        #select_stmt += ";"

        return select_stmt

    def export_query(self, query, file_path, delimiter, rows=5000):
        rowcounts = run_export_query(self._server, self._user, self._password, self._database, self._port, query, file_path,
                         delimiter, rows=5000)
    #    try:
    #        export = self.cursor.execute(query)
    #        rowcounts = 0
    #        while rows:
    #            try:
    #                rows = export.fetchmany(rows)
    #            except:
    #                return rowcounts
    #            rowcount = utils.export_csv(rows, file_path, delimiter)  # Method appends the rows in a file
    #            rowcounts = rowcounts + rowcount
    #    except Exception as e:
    #        logger.error(e)

    def export_table(self,
                     schema,
                     table,
                     columns,
                     path,
                     delimiter=',',
                     replication_key=None,
                     max_replication_key=None,
                     parallelization_key=None):

        # Generate SQL statement for extract
        select_stmt = "SELECT "

        # Add columns
        for col in columns:
            column_name = col[1]
            select_stmt += column_name + ", "
        select_stmt = select_stmt[:-2]

        select_stmt += " FROM " + schema + '.' + table

        # Add incremental where
        if replication_key:
            select_stmt += " WHERE " + replication_key + " > " + "'" + max_replication_key + "'"

        # Add limit
        if self._limit_rows:
            select_stmt += " FETCH FIRST " + str(self._limit_rows) + " ROW ONLY"
        logger.debug(select_stmt)

        # Generate file name
        file_name = self._database + '_' + schema + '_' + table + '.csv'
        file_path = os.path.join(path, file_name)

        total_row_count = self.export_query(select_stmt, file_path, delimiter)

        return path, delimiter, total_row_count


    def export_table_old(self,
                     schema,
                     table,
                     columns,
                     path,
                     delimiter=',',
                     replication_key=None,
                     max_replication_key=None,
                     parallelization_key=None):
        try:
            # Add logic for parallelization_key
            if parallelization_key:
                min_parallelization_key, max_parallelization_key, batch_size_key = self.get_min_max_batch(
                    schema + '.' + table,
                    parallelization_key)
                batch_id = 1
                batch_start = min_parallelization_key
                total_row_count = 0
                cmds_files = []
                cmds_commands = []
                while batch_start < max_parallelization_key:
                    file_name = self._database + "_" + schema + "_" + table + "_" + str(batch_id) + ".csv"
                    file_path = os.path.join(path, file_name)
                    parallelization_where = parallelization_key + ' between ' + str(batch_start) + ' and ' + str(batch_start + batch_size_key - 1)
                    batch_stmt = self.generate_spool_query(columns, delimiter, schema, table, replication_key, max_replication_key, parallelization_where)
                    spool_cmd = self.generate_spool_cmd(file_path, batch_stmt)

                    sql_file = os.path.join(path, self._database + "_" + schema + "_" + table + "_" + str(batch_id) + ".sql")
                    with open(sql_file, "w") as text_file:
                        text_file.write(spool_cmd)

                    cmd = self.generate_cmd_file(sql_file)
                    cmd_file = os.path.join(path, self._database + "_" + schema + "_" + table + "_" + str(batch_id) + ".cmd")
                    with open(cmd_file, "w") as text_file:
                        text_file.write(cmd)

                    cmds_files.append(cmd_file)

                    cmd_commands = self.generate_cmd_command(sql_file)
                    cmds_commands.append(cmd_commands)
                    batch_start += batch_size_key
                    batch_id += 1

                table_workers = self._table_parallel_loads
                if len(cmds_files) < table_workers:
                    table_workers = len(cmds_files)

                try:
                    with Executor(max_workers=table_workers) as executor:
                        for row_count in executor.map(run_export_cmd, cmds_commands):
                        #for row_count in executor.map(run_export_cmd, cmds_files):
                            total_row_count += row_count
                except Exception as exc:
                    logger.error(exc)

            else:
                # Generate SQL statement for extract
                select_stmt = self.generate_spool_query(columns, delimiter, schema, table, replication_key, max_replication_key)

                # Generate file name
                file_name = self._database + "_" + schema + "_" + table + ".csv"
                file_path = os.path.join(path, file_name)

                spool_cmd = self.generate_spool_cmd(file_path, select_stmt)

                sql_file = os.path.join(path, self._database + "_" + schema + "_" + table + ".sql")
                with open(sql_file, "w") as text_file:
                    text_file.write(spool_cmd)

                cmd = self.generate_cmd_file(sql_file)
                cmd_file = os.path.join(path, self._database + "_" + schema + "_" + table + ".cmd")
                with open(cmd_file, "w") as text_file:
                    text_file.write(cmd)
                    os.chmod(cmd_file, 0o0777)

                cmd_commands = self.generate_cmd_command(sql_file)

                #total_row_count = run_export_cmd(cmd_file)
                total_row_count = run_export_cmd(cmd_commands)

            return path, delimiter, None
        except:
            logger.error("Failed exporting table: " + schema + '.' + table)

    def insert_from_table_and_drop(self, schema, to_table, from_table):
        return 'Not implemented for this adapter'

    def switch_tables(self, schema, old_table, new_table):
        return 'Not implemented for this adapter'

    def import_table(self, schema, table, file, delimiter=','):
        return 'Not implemented for this adapter'

    def generate_create_table_ddl(self, schema, table, columns):
        return 'Not implemented for this adapter'

    def create_table_from_columns(self, schema, table, columns):
        return 'Not implemented for this adapter'

    def create_log_table(self, schema, table):
        return 'Not implemented for this adapter'

    def log(self, schema, table,
            project=None,
            project_started_at=None,
            source_table=None,
            target_table=None,
            started_at=None,
            ended_at=None,
            status=None,
            exported_rows=None,
            imported_rows=None):
        return 'Not implemented for this adapter'
