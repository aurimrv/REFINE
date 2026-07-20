# OpenAPI Spec vs. Implementation — Discrepancy Report

**Generated at:** 2026-04-07T17:07:56  
**Specification file:** `/local/ar_benchmark/api-test-generator-impls/experiment/projects/restcountries/specification/original/restcountries_original.json`  
**Source code directory:** `/local/ar_benchmark/api-test-generator-impls/experiment/projects/restcountries`  

## Executive Summary

| Metric | Count |
|---|---|
| Total endpoints analyzed | 27 |
| Fully aligned (MATCH) | 0 |
| Missing in implementation (MISSING_IN_IMPL) | 0 |
| Missing in specification (MISSING_IN_SPEC) | 5 |
| Response code mismatches (RETCODE_MISMATCH) | 22 |
| Parameter mismatches (PARAM_MISMATCH) | 0 |

## Endpoints Implemented but Missing in Specification

### `GET /v1`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `200`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

### `GET /v2`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `200`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

### `POST /contribute`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `202`, `400`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

### `POST /v1`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `405`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

### `POST /v2`

**Category:** `MISSING_IN_SPEC`  
**Impl response codes:** `405`  
**Notes:** Endpoint is implemented in the source code but absent from the spec.  

## Response Code Mismatches

### `GET /v1/all`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: [].  

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
**Impl response codes:** `200`, `400`, `404`  
**Spec parameters:** `alphacode` (path)  
**Impl parameters:** `alphacode` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404'].  

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

### `GET /v2/all`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`  
**Spec parameters:** `fields` (query)  
**Impl parameters:** `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: [].  

### `GET /v2/alpha`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `400`, `404`, `500`  
**Spec parameters:** `fields` (query), `codes` (query)  
**Impl parameters:** `codes` (query), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404', '500'].  

### `GET /v2/alpha/{alphacode}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `400`, `404`  
**Spec parameters:** `fields` (query), `alphacode` (path)  
**Impl parameters:** `alphacode` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404'].  

### `GET /v2/callingcode/{callingcode}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `callingcode` (path)  
**Impl parameters:** `callingcode` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/capital/{capital}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `capital` (path)  
**Impl parameters:** `capital` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/currency/{currency}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `400`, `404`, `500`  
**Spec parameters:** `fields` (query), `currency` (path)  
**Impl parameters:** `currency` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['400', '404', '500'].  

### `GET /v2/demonym/{demonym}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `demonym` (path)  
**Impl parameters:** `demonym` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/lang/{lang}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `lang` (path)  
**Impl parameters:** `lang` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/name/{name}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `name` (path), `fullText` (query)  
**Impl parameters:** `name` (path), `fullText` (query), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/region/{region}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `region` (path)  
**Impl parameters:** `region` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/regionalbloc/{regionalbloc}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `regionalbloc` (path)  
**Impl parameters:** `regionalbloc` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

### `GET /v2/subregion/{subregion}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`, `default`  
**Impl response codes:** `200`, `404`, `500`  
**Spec parameters:** `fields` (query), `subregion` (path)  
**Impl parameters:** `subregion` (path), `fields` (query)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['404', '500'].  

---
*Report generated by OpenAPI Spec Improver on 2026-04-07T17:07:56.*
