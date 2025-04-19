# RAG Setup

## pgvector

```
brew install postgresql
```

```
brew services list
```

```
brew services start postgresql@14
```

```
psql --version
```

```
psql (PostgreSQL) 14.16 (Homebrew)
```

Connect to the server

```
psql -U postgres -W
```


List of databases

```
psql -l
```

Create the database for RAG embeddings

```
CREATE DATABASE pgvector_rag;
\c pgvector_rag
```

```
CREATE EXTENSION vector;
```

If you receive an error

```
ERROR:  could not open extension control file "/opt/homebrew/share/postgresql@14/extension/vector.control": No such file or directory
```

the install pgvector via another terminal

```
export PG_CONFIG=/opt/homebrew/bin/pg_config
```

```
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
```

```
make
make install
```

```
ls /opt/homebrew/share/postgresql@14/extension/vector.control
```

Try again

```
CREATE EXTENSION vector;
```


No tables, relations at this time as it is a newly created database

```
\d
```

```
Did not find any relations.
```

Quit psql (or use another terminal)

```
\q
```

## Load Sample data

```
python 1-ingestion-from-directory-no-riddle.py
```

The no-riddle and with-riddle just plays with the chunking size.  Depending on chunking size+overlap it either correctly or incorrectly answers "What is the Mad Hatter's riddle?"


