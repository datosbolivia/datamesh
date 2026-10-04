# Package-level environment holding C-ABI library reference and cache
.datamesh_env <- new.env(parent = emptyenv())
.datamesh_env$lib <- NULL
.datamesh_env$default_catalog_url <- "https://datosbolivia.github.io/llms.txt"

.onLoad <- function(libname, pkgname) {
  # Look for compiled Go core shared library libdatamesh.so / libdatamesh.dylib / datamesh.dll
  lib_path <- Sys.getenv("DATAMESH_LIB_PATH", "")
  if (lib_path == "" || !file.exists(lib_path)) {
    candidates <- c(
      "libdatamesh.so",
      "libdatamesh.dylib",
      "datamesh.dll",
      file.path(system.file(package = "datamesh"), "libs", "libdatamesh.so"),
      file.path(getwd(), "libdatamesh.so"),
      file.path(getwd(), "core-go", "libdatamesh.so")
    )
    for (cand in candidates) {
      if (file.exists(cand)) {
        lib_path <- cand
        break
      }
    }
  }

  if (lib_path != "" && file.exists(lib_path)) {
    tryCatch({
      dyn.load(lib_path)
      .datamesh_env$lib <- lib_path
      # Initialize runtime via C-ABI
      .C("DataMeshInit", as.character(""), res = character(1))
    }, error = function(e) {
      .datamesh_env$lib <- NULL
    })
  }
}

#' Call Go Core C-ABI function returning parsed JSON response
#' @keywords internal
.call_c_abi <- function(func_name, ...) {
  if (is.null(.datamesh_env$lib)) return(NULL)
  tryCatch({
    args <- list(...)
    c_args <- lapply(args, function(x) {
      if (is.null(x)) "" else as.character(x)
    })
    res_raw <- do.call(.Call, c(list(func_name), c_args))
    if (!is.null(res_raw)) {
      parsed <- jsonlite::fromJSON(res_raw)
      if (isTRUE(parsed$success)) return(parsed$data)
    }
    NULL
  }, error = function(e) {
    NULL
  })
}

#' Discover sovereign federated data catalogs
#'
#' @param catalog_url Optional catalog URL or llms.txt endpoint. If omitted, uses default or DATAMESH_CATALOG_URL.
#' @return A list containing catalog title, source_catalogs, and entries data.frame.
#' @export
datamesh_discover <- function(catalog_url = NULL) {
  # 1. Try Go Core C-ABI first
  c_res <- .call_c_abi("DataMeshDiscoverCatalog", catalog_url)
  if (!is.null(c_res)) return(c_res)

  # 2. Pure R Fallback implementation
  target <- catalog_url
  if (is.null(target) || target == "") {
    target <- Sys.getenv("DATAMESH_CATALOG_URL", .datamesh_env$default_catalog_url)
  }

  lines <- tryCatch({
    readLines(target, warn = FALSE, encoding = "UTF-8")
  }, error = function(e) {
    stop(sprintf("Failed to fetch catalog from '%s': %s", target, e$message))
  })

  title <- "DataMesh Federated Catalog"
  description <- ""
  entries <- list()

  entry_regex <- "^-\\s*\\[(.*?)\\]\\((.*?)\\)(?::\\s*(.*))?$"
  domain_regex <- "\\(Dominio:\\s*([^)]*?)(?:\\.|\\)|Recursos:)"

  for (line in lines) {
    line <- trimws(line)
    if (line == "") next
    if (startsWith(line, "# ") && title == "DataMesh Federated Catalog") {
      title <- trimws(substring(line, 3))
      next
    }
    if (startsWith(line, "> ") && description == "") {
      description <- trimws(substring(line, 3))
      next
    }

    if (grepl(entry_regex, line)) {
      m <- regexec(entry_regex, line)[[1]]
      matches <- regmatches(line, list(m))[[1]]
      item_title <- matches[2]
      raw_uri <- matches[3]
      desc_text <- if (length(matches) >= 4) matches[4] else ""

      resolved_url <- raw_uri
      if (!grepl("^https?://", raw_uri)) {
        base_dir <- dirname(target)
        resolved_url <- file.path(base_dir, raw_uri)
      }

      domain_name <- ""
      if (grepl(domain_regex, desc_text)) {
        dm <- regexec(domain_regex, desc_text)[[1]]
        dmatches <- regmatches(desc_text, list(dm))[[1]]
        if (length(dmatches) >= 2) domain_name <- trimws(dmatches[2])
      }

      clean_desc <- trimws(strsplit(desc_text, "\\(Dominio:")[[1]][1])

      entries[[length(entries) + 1]] <- list(
        title = item_title,
        uri = raw_uri,
        resolved_url = resolved_url,
        description = clean_desc,
        domain = domain_name,
        catalog_source = target
      )
    }
  }

  list(
    title = title,
    description = description,
    source_catalogs = list(target),
    entries = do.call(rbind, lapply(entries, as.data.frame))
  )
}

#' Search data products across sovereign catalogs by keyword
#'
#' @param keyword Search keyword matching title, description, or domain.
#' @param catalog_url Optional catalog URL.
#' @return A data.frame of matching catalog entries.
#' @export
datamesh_search <- function(keyword, catalog_url = NULL) {
  # 1. Try Go Core C-ABI
  c_res <- .call_c_abi("DataMeshSearchCatalog", keyword, catalog_url)
  if (!is.null(c_res)) return(as.data.frame(c_res))

  # 2. Pure R Fallback
  cat <- datamesh_discover(catalog_url)
  df <- cat$entries
  if (nrow(df) == 0) return(df)

  kw <- tolower(trimws(keyword))
  matches <- grepl(kw, tolower(df$title)) |
             grepl(kw, tolower(df$description)) |
             grepl(kw, tolower(df$domain))

  df[matches, , drop = FALSE]
}

#' Resolve and validate an OKF v0.2 Data Product manifest
#'
#' @param uri_or_url Sovereign node URI or HTTP URL.
#' @return A list representing the validated DataProduct.
#' @export
datamesh_get <- function(uri_or_url) {
  # 1. Try Go Core C-ABI
  c_res <- .call_c_abi("DataMeshResolveDataProduct", uri_or_url)
  if (!is.null(c_res)) return(c_res)

  # 2. Pure R Fallback
  target <- trimws(uri_or_url)
  if (!grepl("^https?://", target) && !grepl("^file://", target)) {
    cat <- datamesh_discover()
    entries <- cat$entries
    match_row <- entries[tolower(entries$title) == tolower(target) | grepl(tolower(target), tolower(entries$uri)), ]
    if (nrow(match_row) > 0) {
      target <- match_row$resolved_url[1]
    }
  }

  if (endsWith(target, "/")) target <- paste0(target, "index.md")
  if (!grepl("\\.(md|yaml|json)$", target)) target <- paste0(target, "/index.md")

  lines <- tryCatch({
    readLines(target, warn = FALSE, encoding = "UTF-8")
  }, error = function(e) {
    stop(sprintf("Failed to resolve Data Product at '%s': %s", target, e$message))
  })

  content <- paste(lines, collapse = "\n")
  parts <- strsplit(content, "---")[[1]]

  manifest <- list(type = "dataset", title = uri_or_url, dimensions = list(), lineage = list(version = "1.0.0"))
  description <- ""

  if (length(parts) >= 3) {
    description <- trimws(paste(parts[3:length(parts)], collapse = "---"))
    front_lines <- strsplit(parts[2], "\n")[[1]]
    for (fl in front_lines) {
      fl <- trimws(fl)
      if (startsWith(fl, "title:")) manifest$title <- trimws(gsub("['\"]", "", substring(fl, 7)))
      if (startsWith(fl, "type:")) manifest$type <- trimws(gsub("['\"]", "", substring(fl, 6)))
      if (startsWith(fl, "- ") && "dimensions" %in% names(manifest)) {
        manifest$dimensions[[length(manifest$dimensions) + 1]] <- trimws(gsub("['\"]", "", substring(fl, 3)))
      }
    }
  } else {
    description <- content
  }

  list(
    id = uri_or_url,
    manifest = manifest,
    description = description,
    raw_content = content
  )
}

#' Query tabular resource with optional column filters and limit
#'
#' @param resource_uri Direct HTTP URL, local path, or canonical triad.
#' @param filters Named list or vector of column equality filters.
#' @param limit Maximum rows to return.
#' @return A data.frame containing the queried dataset.
#' @export
datamesh_query <- function(resource_uri, filters = NULL, limit = NULL) {
  opts <- list()
  if (!is.null(filters)) opts$filters <- as.list(filters)
  if (!is.null(limit)) opts$limit <- as.integer(limit)
  opts_json <- jsonlite::toJSON(opts, auto_unbox = TRUE)

  # 1. Try Go Core C-ABI
  c_res <- .call_c_abi("DataMeshQueryResource", resource_uri, opts_json)
  if (!is.null(c_res) && !is.null(c_res$columns) && !is.null(c_res$rows)) {
    df <- as.data.frame(do.call(rbind, c_res$rows), stringsAsFactors = FALSE)
    colnames(df) <- c_res$columns
    return(df)
  }

  # 2. Pure R Fallback
  df <- tryCatch({
    read.csv(resource_uri, stringsAsFactors = FALSE, check.names = FALSE)
  }, error = function(e) {
    stop(sprintf("Failed to read tabular resource from '%s': %s", resource_uri, e$message))
  })

  if (!is.null(filters)) {
    for (col_name in names(filters)) {
      match_col <- colnames(df)[tolower(colnames(df)) == tolower(col_name)]
      if (length(match_col) > 0) {
        val <- as.character(filters[[col_name]])
        df <- df[as.character(df[[match_col[1]]]) == val, , drop = FALSE]
      }
    }
  }

  if (!is.null(limit) && limit > 0 && nrow(df) > limit) {
    df <- df[seq_len(limit), , drop = FALSE]
  }

  df
}

#' Execute full ANSI SQL with canonical triads and DuckDB
#'
#' @param sql_query Full ANSI SQL query referencing tables as 'catalogo:dataset:resource', 'cat/ds/res', or direct URLs.
#' @param table_mapping Optional named list mapping table names to local paths or URLs.
#' @return A data.frame with query results.
#' @export
datamesh_sql <- function(sql_query, table_mapping = NULL) {
  # 1. Try DuckDB R adapter if available
  if (requireNamespace("duckdb", quietly = TRUE) && requireNamespace("DBI", quietly = TRUE)) {
    con <- DBI::dbConnect(duckdb::duckdb(), dbdir = ":memory:")
    on.exit(DBI::dbDisconnect(con, shutdown = TRUE))

    tryCatch({
      DBI::dbExecute(con, "INSTALL httpfs; LOAD httpfs;")
    }, error = function(e) NULL)

    if (!is.null(table_mapping)) {
      for (tbl_name in names(table_mapping)) {
        p <- table_mapping[[tbl_name]]
        read_expr <- if (grepl("\\.parquet$", p, ignore.case = TRUE)) {
          sprintf("read_parquet('%s')", p)
        } else {
          sprintf("read_csv_auto('%s')", p)
        }
        view_sql <- sprintf('CREATE OR REPLACE VIEW "%s" AS SELECT * FROM %s', tbl_name, read_expr)
        DBI::dbExecute(con, view_sql)
      }
    }

    res <- DBI::dbGetQuery(con, sql_query)
    return(res)
  }

  # 2. Try Go Core C-ABI execution
  opts <- list(engine_name = "inmem", table_mapping = as.list(table_mapping))
  c_res <- .call_c_abi("DataMeshExecuteSQL", sql_query, jsonlite::toJSON(opts, auto_unbox = TRUE))
  if (!is.null(c_res) && !is.null(c_res$columns) && !is.null(c_res$rows)) {
    df <- as.data.frame(do.call(rbind, c_res$rows), stringsAsFactors = FALSE)
    colnames(df) <- c_res$columns
    return(df)
  }

  stop("datamesh_sql requires the 'duckdb' R package or compiled 'libdatamesh.so' library.")
}

# 1-line ergonomic aliases matching Python / TS naming
dm_discover <- datamesh_discover
dm_search <- datamesh_search
dm_get <- datamesh_get
dm_query <- datamesh_query
dm_sql <- datamesh_sql
