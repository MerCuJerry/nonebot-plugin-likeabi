import sqlite3,os

class _sql:
    '数据库连接类'
    likeabi_sql:sqlite3.Connection
    def __init__(self, path):
        sqlpath=os.path.join(path,'likeabi.db')
        if os.path.isfile(sqlpath):
            self.likeabi_sql=sqlite3.connect(sqlpath)
        else:
            self.likeabi_sql=sqlite3.connect(sqlpath)
            self.likeabi_sql.execute("CREATE TABLE LIKEABI(QID INT PRIMARY KEY    NOT NULL,LIKEABINUM INT    NOT NULL);")
            self.likeabi_sql.commit()

    def sql_create(self, table : str):
        try:
            self.likeabi_sql.execute("CREATE TABLE "+table+"(QID INT PRIMARY KEY    NOT NULL,LIKEABINUM INT    NOT NULL);")
        except:
            pass
        
    def sql_del(self, table : str, qid):
        try:
            sql_list=(qid,)
            self.likeabi_sql.execute("DELETE from "+table+" where QID=?",sql_list)
            self.likeabi_sql.commit()
        except:
            pass
            
    def sql_select(self, table : str, qid):
        try:
            sql_list=(qid,)
            sql_setence="SELECT LIKEABINUM from "+table+" where QID=?"
            now = self.likeabi_sql.execute(sql_setence, sql_list).fetchone()
            if now is None:
                return None
            else:
                return now[0]
        except:
            return -1
    
    def sql_insert_update(self, table : str, qid, num):
        try:
            if self.likeabi_sql.execute("SELECT name from sqlite_master where tbl_name=?",(table,)).fetchone() is None:
                self.sql_create(table)
            now = self.sql_select(table, qid)
            if now is None:
                sql_list=(qid,num)
                self.likeabi_sql.execute("INSERT into "+table+" VALUES (?,?)",sql_list)
            else:
                sql_list=(num+now,qid)
                self.likeabi_sql.execute("UPDATE "+table+" set LIKEABINUM=? where QID=?",sql_list)
            self.likeabi_sql.commit()
        except:
            pass
    
    def sql_del_other(self):
        tables = self.likeabi_sql.execute("SELECT tbl_name from sqlite_master")
        for raw in tables:
            if raw[0] != "LIKEABI":
                self.likeabi_sql.execute("DELETE from "+raw[0])
        self.likeabi_sql.commit()
        
    def __del__(self):
        self.likeabi_sql.close()