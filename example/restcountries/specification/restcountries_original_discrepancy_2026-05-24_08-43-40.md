# OpenAPI Spec vs. Implementation — Discrepancy Report

**Generated at:** 2026-05-24T08:45:27  
**Specification file:** `/local/ar_benchmark/artigo-sbes-refine/REFINE/example/restcountries/specification/restcountries_original.json`  
**Source code directory:** `/local/ar_benchmark/artigo-sbes-refine/REFINE/example/restcountries`  

## Executive Summary

| Metric | Count |
|---|---|
| Total endpoints analyzed | 25 |
| Fully aligned (MATCH) | 0 |
| Missing in implementation (MISSING_IN_IMPL) | 12 |
| Missing in specification (MISSING_IN_SPEC) | 3 |
| Response code mismatches (RETCODE_MISMATCH) | 10 |
| Parameter mismatches (PARAM_MISMATCH) | 0 |

## Endpoints Declared in Spec but Missing in Implementation

### `GET /v2/all`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/alpha`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/alpha/{alphacode}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/callingcode/{callingcode}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/capital/{capital}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/currency/{currency}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/demonym/{demonym}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/lang/{lang}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/name/{name}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/region/{region}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/regionalbloc/{regionalbloc}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

### `GET /v2/subregion/{subregion}`

**Category:** `MISSING_IN_IMPL`  
**Spec response codes:** `200`, `default`  
**Notes:** Endpoint is declared in the spec but not found in the source code.  

## Endpoints Implemented but Missing in Specification

### `GET /v1`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `200`, `500`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

### `POST /contribute`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `202`, `400`, `500`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

### `POST /v1`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `405`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

## Response Code Mismatches

### `GET /v1/all`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `500`  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['500'].  

### `GET /v1/alpha`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `400`, `404`, `500`  
**Spec parameters:** `codes` (query)  
**Impl parameters:** `codes` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404', '500'].  

### `GET /v1/alpha/{alphacode}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `400`, `404`, `500`  
**Spec parameters:** `alphacode` (path)  
**Impl parameters:** `alphacode` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404', '500'].  

### `GET /v1/callingcode/{callingcode}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `callingcode` (path)  
**Impl parameters:** `callingcode` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v1/capital/{capital}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `capital` (path)  
**Impl parameters:** `capital` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v1/currency/{currency}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `400`, `404`, `500`  
**Spec parameters:** `currency` (path)  
**Impl parameters:** `currency` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404', '500'].  

### `GET /v1/lang/{lang}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `lang` (path)  
**Impl parameters:** `lang` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v1/name/{name}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `name` (path), `fullText` (query)  
**Impl parameters:** `name` (path), `fullText` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v1/region/{region}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `region` (path)  
**Impl parameters:** `region` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v1/subregion/{subregion}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `subregion` (path)  
**Impl parameters:** `subregion` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

---
*Report generated by OpenAPI Spec Improver on 2026-05-24T08:45:27.*
