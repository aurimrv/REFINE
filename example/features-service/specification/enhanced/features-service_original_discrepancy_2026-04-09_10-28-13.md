# OpenAPI Spec vs. Implementation — Discrepancy Report

**Generated at:** 2026-04-09T10:30:38  
**Specification file:** `/local/ar_benchmark/api-test-generator-impls/api-spec-improver/examples/features-service/features-service_original.json`  
**Source code directory:** `/local/ar_benchmark/api-test-generator-impls/experiment/projects/features-service`  

## Executive Summary

| Metric | Count |
|---|---|
| Total endpoints analyzed | 18 |
| Fully aligned (MATCH) | 0 |
| Missing in implementation (MISSING_IN_IMPL) | 0 |
| Missing in specification (MISSING_IN_SPEC) | 0 |
| Response code mismatches (RETCODE_MISMATCH) | 18 |
| Parameter mismatches (PARAM_MISMATCH) | 0 |

## Response Code Mismatches

### `DELETE /products/{productname}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `204`, `500`  
**Spec parameters:** `productName` (path)  
**Impl parameters:** `productName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['204', '500'].  

### `DELETE /products/{productname}/configurations/{configurationname}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `204`, `500`  
**Spec parameters:** `productName` (path), `configurationName` (path)  
**Impl parameters:** `productName` (path), `configurationName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['204', '500'].  

### `DELETE /products/{productname}/configurations/{configurationname}/features/{featurename}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `204`, `500`  
**Spec parameters:** `productName` (path), `configurationName` (path), `featureName` (path)  
**Impl parameters:** `productName` (path), `configurationName` (path), `featureName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['204', '500'].  

### `DELETE /products/{productname}/constraints/{constraintid}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `204`, `500`  
**Spec parameters:** `productName` (path), `constraintId` (path)  
**Impl parameters:** `productName` (path), `constraintId` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['204', '500'].  

### `DELETE /products/{productname}/features/{featurename}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `204`, `500`  
**Spec parameters:** `productName` (path), `featureName` (path)  
**Impl parameters:** `productName` (path), `featureName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['204', '500'].  

### `GET /products`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Notes:** Response codes only in spec: []. Response codes only in impl: ['500'].  

### `GET /products/{productname}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Spec parameters:** `productName` (path)  
**Impl parameters:** `productName` (path)  
**Notes:** Response codes only in spec: []. Response codes only in impl: ['500'].  

### `GET /products/{productname}/configurations`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Spec parameters:** `productName` (path)  
**Impl parameters:** `productName` (path)  
**Notes:** Response codes only in spec: []. Response codes only in impl: ['500'].  

### `GET /products/{productname}/configurations/{configurationname}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Spec parameters:** `productName` (path), `configurationName` (path)  
**Impl parameters:** `productName` (path), `configurationName` (path)  
**Notes:** Response codes only in spec: []. Response codes only in impl: ['500'].  

### `GET /products/{productname}/configurations/{configurationname}/features`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Spec parameters:** `productName` (path), `configurationName` (path)  
**Impl parameters:** `productName` (path), `configurationName` (path)  
**Notes:** Response codes only in spec: []. Response codes only in impl: ['500'].  

### `GET /products/{productname}/features`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Spec parameters:** `productName` (path)  
**Impl parameters:** `productName` (path)  
**Notes:** Response codes only in spec: []. Response codes only in impl: ['500'].  

### `POST /products/{productname}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `201`, `500`  
**Spec parameters:** `productName` (path)  
**Impl parameters:** `productName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['201', '500'].  

### `POST /products/{productname}/configurations/{configurationname}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `201`, `500`  
**Spec parameters:** `productName` (path), `configurationName` (path)  
**Impl parameters:** `productName` (path), `configurationName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['201', '500'].  

### `POST /products/{productname}/configurations/{configurationname}/features/{featurename}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `201`, `500`  
**Spec parameters:** `productName` (path), `configurationName` (path), `featureName` (path)  
**Impl parameters:** `productName` (path), `configurationName` (path), `featureName` (path)  
**Notes:** Response codes only in spec: ['default']. Response codes only in impl: ['201', '500'].  

### `POST /products/{productname}/constraints/excludes`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `201`, `500`  
**Spec parameters:** `productName` (path), `sourceFeature` (formData), `excludedFeature` (formData)  
**Impl parameters:** `productName` (path), `sourceFeature` (form), `excludedFeature` (form)  
**Notes:** Response code mismatch — only in spec: ['default']; only in impl: ['201', '500']. Parameter mismatch — only in spec: [('excludedFeature', 'formData'), ('sourceFeature', 'formData')]; only in impl: [('excludedFeature', 'form'), ('sourceFeature', 'form')].  

### `POST /products/{productname}/constraints/requires`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `201`, `500`  
**Spec parameters:** `productName` (path), `sourceFeature` (formData), `requiredFeature` (formData)  
**Impl parameters:** `productName` (path), `sourceFeature` (form), `requiredFeature` (form)  
**Notes:** Response code mismatch — only in spec: ['default']; only in impl: ['201', '500']. Parameter mismatch — only in spec: [('requiredFeature', 'formData'), ('sourceFeature', 'formData')]; only in impl: [('requiredFeature', 'form'), ('sourceFeature', 'form')].  

### `POST /products/{productname}/features/{featurename}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `default`  
**Impl response codes:** `201`, `500`  
**Spec parameters:** `productName` (path), `featureName` (path), `description` (formData)  
**Impl parameters:** `productName` (path), `featureName` (path), `description` (form)  
**Notes:** Response code mismatch — only in spec: ['default']; only in impl: ['201', '500']. Parameter mismatch — only in spec: [('description', 'formData')]; only in impl: [('description', 'form')].  

### `PUT /products/{productname}/features/{featurename}`

**Category:** `RETCODE_MISMATCH`  
**Spec response codes:** `200`  
**Impl response codes:** `200`, `500`  
**Spec parameters:** `productName` (path), `featureName` (path), `description` (formData)  
**Impl parameters:** `productName` (path), `featureName` (path), `description` (form)  
**Notes:** Response code mismatch — only in spec: []; only in impl: ['500']. Parameter mismatch — only in spec: [('description', 'formData')]; only in impl: [('description', 'form')].  

---
*Report generated by OpenAPI Spec Improver on 2026-04-09T10:30:38.*
