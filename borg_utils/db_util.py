import tempfile
import os
import subprocess
from sqlalchemy import create_engine

from django.conf import settings
from django.db import connection

class _DbUtil(object):
    _query_index_constraint_sql = """
SELECT s.conname ,s.contype
FROM pg_constraint s JOIN pg_class c ON s.conrelid = c.oid JOIN pg_namespace n on c.relnamespace = n.oid 
WHERE n.nspname='{0}' and c.relname='{1}' and s.contype in ('p','u')
"""

    _query_index_sql = """
SELECT ci.relname,i.indisprimary 
FROM pg_index i JOIN pg_class ci ON i.indexrelid = ci.oid JOIN pg_class ct ON i.indrelid = ct.oid JOIN pg_namespace np on ct.relnamespace = np.oid 
WHERE np.nspname='{0}' and ct.relname='{1}'
"""

    _check_table_exist_sql = "SELECT count(1) FROM pg_catalog.pg_class a JOIN pg_catalog.pg_namespace b ON a.relnamespace = b.oid WHERE b.nspname = '{0}' AND a.relname = '{1}'"

    _query_all_tables = "select relname from pg_class c join pg_namespace n on c.relnamespace=n.oid where n.nspname='{schema}' and c.relkind = 'r'"

    _query_all_views = "select relname from pg_class c join pg_namespace n on c.relnamespace=n.oid where n.nspname='{schema}' and c.relkind in ('v','m')"

    """
    a set of utility method to access db
    """
    def __init__(self,name,host="127.0.0.1",port=5432,user="anonymous",password=None,default_schema="public",connection=None):
        self._name = name or "public"
        self._host = host
        self._port = port or 5432
        self._user = user
        self._password = password
        self._default_schema = default_schema

        self._env = None
        self._table_schema_dump_cmd = None
        self._connection = connection
        self._engine = None

    def get_create_table_sql(self,schema,table):
        if not self._env:
            self._env = os.environ.copy()
            if self._password:
                _env["PGPASSWORD"] = _database["PASSWORD"]

            self._table_schema_dump_cmd = ["pg_dump", "-h", self._host, "-d", self._name, "-U", self._user, "-F", "p", "-w", "-x", "-O", "--no-security-labels", "--no-tablespaces", "-s"]
            if self._port:
                self._table_schema_dump_cmd += ["-p", str(self._port)]

        #get the input table structure
        f = tempfile.NamedTemporaryFile(delete=False)
        f.close()
        cmd = DbUtil._table_schema_dump_cmd + ["-t", schema + "." + table, "-f", f.name]
        output = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE, env=DbUtil._env).communicate()
        if output[1].strip() :
            raise Exception(output[1])
        try:
            reader = open(f.name,'r') 
            return ''.join([s for s in reader if not (s.startswith('SET') or s.startswith('--')) and s.strip() ])
        finally:
            if reader:
                reader.close()
            os.unlink(f.name)


    def cursor(self):
        if self._connection:
            return self._connection.cursor()
        else:
            if not self._engine:
                self._engine =  create_engine("postgresql://{3}:{4}@{1}:{2}/{0}".format(self._name,self._host,self._port,self._user,self._password))
            return self._engine.connect()

    def get(self,sql,cursor=None):
        close = False
        if not cursor:
            cursor = self.cursor()
            close = True

        try:
            result = cursor.execute(sql)
            if result:               
                return result.fetchone()
            else:
                return cursor.fetchone()
        finally:
            if close:
                cursor.close()
                cursor = None

    def query(self,sql,cursor=None):
        close = False
        if not cursor:
            cursor = self.cursor()
            close = True

        try:
            result = cursor.execute(sql)
            if result:               
                return sql_result.fetchall()
            else:
                return cursor.fetchall()
        finally:
            if close:
                cursor.close()
                cursor = None

    def update(self,sql,cursor=None):
        close = False
        if not cursor:
            cursor = self.cursor()
            close = True

        try:
            cursor.execute(sql)
        finally:
            if close:
                cursor.close()
                cursor = None


    def drop_all_indexes(self,schema,table,include_pk=False):
        """
        drop all indexes.
        drop primary key also if include_pk is true
        """
        #drop related constraint first
        #import ipdb;ipdb.set_trace()
        cursor = None
        try:
            cursor = self.cursor()
            rows = self.query(self._query_index_constraint_sql.format(schema,table),cursor)
            drop_constraint_sql = "\r\n".join(["ALTER TABLE \"{0}\".{1} DROP CONSTRAINT IF EXISTS {2} CASCADE;".format(schema,table,r[0]) for r in rows if r[1] != 'p' or include_pk ])
            if drop_constraint_sql:
                self.update(drop_constraint_sql,cursor)

            rows = self.query(self._query_index_sql.format(schema,table),cursor)
            drop_index_sql = "\r\n".join(["DROP INDEX IF EXISTS \"{0}\".\"{1}\" CASCADE;".format(schema,r[0]) for r in rows if not r[1] or include_pk ])
            if drop_index_sql:
                self.update(drop_index_sql,cursor)
        finally:
            if cursor:
                cursor.close()


    def table_exists(self,table,schema=None):
        result = self.get(self._check_table_exist_sql.format(schema or self._default_schema,table))
        return result[0] and True or False

    def exists(self,sql):
        result = self.get(sql)
        return result[0] and True or False

    def _user_tables(self,name):
        name = name.lower()
        return not any([name[:len(reserved_name)] == reserved_name for reserved_name in ["django_","spatial_ref_sys","reversion","auth","geography_columns","geometry_columns","raster_","pg_"] ])

    def get_all_tables(self,schema=None):
        rows = self.query(self._query_all_tables.format(schema=schema or self._default_schema))
        tables = [row[0] for row in rows if self._user_tables(row[0])]
        return tables;

    def get_all_views(self,schema=None):
        rows = self.query(self._query_all_views.format(schema=schema or self._default_schema))
        views = [row[0] for row in rows if self._user_tables(row[0])]
        return views;


_DB_UTILS = {
}

def DbUtil(name,host="127.0.0.1",port=5432,user=None,password=None,default_schema="public",connection=None):
    name = name or "public"
    port = port or 5432
    host = host or "127.0.0.1"
    dbname = "postgresql://{1}:{2}/{0}".format(name,host,port)
    if dbname not in _DB_UTILS:
        _DB_UTILS[dbname] = _DbUtil(name,host,port,user,password,default_schema,connection)

    return _DB_UTILS[dbname]


_database = settings.DATABASES["default"]
defaultDbUtil = DbUtil(_database["NAME"],_database["HOST"],_database.get("PORT",5432),_database["USER"],_database.get("PASSWORD"),_database.get("SCHEMA","public"),connection)

