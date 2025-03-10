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

