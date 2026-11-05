// Generated from docs/architecture/contracts/foundation.openapi.json.
// Do not edit. Run `pnpm --filter @jev-rag/web generate:api` to regenerate.

export interface paths {
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Process liveness only. Never calls external dependencies. */
        get: operations["getLiveness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Bounded Qdrant connectivity check. TypeSafe availability does not affect readiness. An unconfigured probe reports down. */
        get: operations["getReadiness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/system/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Minimal process status for the frontend. Never calls external dependencies and does not imply Qdrant readiness. */
        get: operations["getSystemStatus"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * @example {
         *       "status": "alive"
         *     }
         */
        LivenessResponse: {
            /** @constant */
            status: "alive";
        };
        /**
         * @example {
         *       "status": "ready",
         *       "dependencies": {
         *         "qdrant": "up"
         *       }
         *     }
         */
        ReadinessResponse: {
            /** @constant */
            status: "ready";
            dependencies: {
                /** @constant */
                qdrant: "up";
            };
        };
        /**
         * @example {
         *       "status": "not_ready",
         *       "dependencies": {
         *         "qdrant": "down"
         *       }
         *     }
         */
        NotReadyResponse: {
            /** @constant */
            status: "not_ready";
            dependencies: {
                /** @constant */
                qdrant: "down";
            };
        };
        /**
         * @example {
         *       "service": "api",
         *       "status": "ok"
         *     }
         */
        SystemStatusResponse: {
            /** @constant */
            service: "api";
            /** @constant */
            status: "ok";
        };
        ValidationDetail: {
            field: string;
            code: string;
        };
        /**
         * @example {
         *       "error": {
         *         "code": "VALIDATION_ERROR",
         *         "message": "Invalid request",
         *         "details": [
         *           {
         *             "field": "body.question",
         *             "code": "required"
         *           }
         *         ]
         *       },
         *       "request_id": "80d3c0b6-9b52-4aa9-85a0-5a657bb402d8"
         *     }
         */
        ErrorResponse: {
            error: {
                code: string;
                message: string;
                details: null | components["schemas"]["ValidationDetail"][];
            };
            request_id: string;
        };
    };
    responses: {
        /** @description Unexpected application failure. Code INTERNAL_ERROR, message Internal server error, details null. */
        InternalError: {
            headers: {
                "X-Request-ID": components["headers"]["RequestId"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Unknown endpoint. Code NOT_FOUND, message Resource not found, details null. */
        NotFound: {
            headers: {
                "X-Request-ID": components["headers"]["RequestId"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Unsupported HTTP method. Code METHOD_NOT_ALLOWED, message Method not allowed, details null. */
        MethodNotAllowed: {
            headers: {
                "X-Request-ID": components["headers"]["RequestId"];
                /** @description Allowed HTTP methods for this resource. */
                Allow: string;
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Invalid request. Code VALIDATION_ERROR, message Invalid request, sanitized details only. */
        ValidationError: {
            headers: {
                "X-Request-ID": components["headers"]["RequestId"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Future business dependency failure. Code SERVICE_UNAVAILABLE, message Service unavailable, details null. Readiness uses NotReadyResponse instead. */
        ServiceUnavailable: {
            headers: {
                "X-Request-ID": components["headers"]["RequestId"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Standard error envelope, except the documented readiness dependency failure. */
        Error: {
            headers: {
                "X-Request-ID": components["headers"]["RequestId"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
    };
    parameters: {
        /** @description Accept 1-64 ASCII letters, digits, dot, underscore or hyphen. Missing or invalid values are replaced by UUID4, not rejected as validation errors. */
        RequestId: string;
    };
    requestBodies: never;
    headers: {
        /** @description Correlation ID on every response. Equals request_id in an error body. A valid incoming ID is preserved, otherwise UUID4 is generated. */
        RequestId: string;
    };
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getLiveness: {
        parameters: {
            query?: never;
            header?: {
                /** @description Accept 1-64 ASCII letters, digits, dot, underscore or hyphen. Missing or invalid values are replaced by UUID4, not rejected as validation errors. */
                "X-Request-ID"?: components["parameters"]["RequestId"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful diagnostic response. */
            200: {
                headers: {
                    "X-Request-ID": components["headers"]["RequestId"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LivenessResponse"];
                };
            };
            500: components["responses"]["InternalError"];
            default: components["responses"]["Error"];
        };
    };
    getReadiness: {
        parameters: {
            query?: never;
            header?: {
                /** @description Accept 1-64 ASCII letters, digits, dot, underscore or hyphen. Missing or invalid values are replaced by UUID4, not rejected as validation errors. */
                "X-Request-ID"?: components["parameters"]["RequestId"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful diagnostic response. */
            200: {
                headers: {
                    "X-Request-ID": components["headers"]["RequestId"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadinessResponse"];
                };
            };
            500: components["responses"]["InternalError"];
            /** @description Qdrant is unavailable. This diagnostic response intentionally differs from the standard error envelope. */
            503: {
                headers: {
                    "X-Request-ID": components["headers"]["RequestId"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotReadyResponse"];
                };
            };
            default: components["responses"]["Error"];
        };
    };
    getSystemStatus: {
        parameters: {
            query?: never;
            header?: {
                /** @description Accept 1-64 ASCII letters, digits, dot, underscore or hyphen. Missing or invalid values are replaced by UUID4, not rejected as validation errors. */
                "X-Request-ID"?: components["parameters"]["RequestId"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful diagnostic response. */
            200: {
                headers: {
                    "X-Request-ID": components["headers"]["RequestId"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SystemStatusResponse"];
                };
            };
            500: components["responses"]["InternalError"];
            default: components["responses"]["Error"];
        };
    };
}
