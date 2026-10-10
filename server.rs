use axum::{
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use unluac::decompile::{decompile, DecompileOptions};

#[derive(Deserialize)]
struct DecompileRequest {
    bytecode: String, // Base64 encoded
    dialect: String,
}

#[derive(Serialize)]
struct DecompileResponse {
    source: String,
    success: bool,
    error: Option<String>,
}

async fn handle_decompile(Json(payload): Json<DecompileRequest>) -> Json<DecompileResponse> {
    // Decode Base64 bytecode
    let bytes = match base64::decode(&payload.bytecode) {
        Ok(b) => b,
        Err(e) => return Json(DecompileResponse {
            source: "".into(),
            success: false,
            error: Some(format!("Base64 decode error: {}", e)),
        }),
    };

    // Configure options based on requested dialect
    let options = DecompileOptions::default(); // In real impl, map payload.dialect to enum

    match decompile(&bytes, options) {
        Ok(result) => {
            let source = result.state.generated
                .as_ref()
                .map(|g| g.source.clone())
                .unwrap_or_else(|| "No source generated".into());

            Json(DecompileResponse {
                source,
                success: true,
                error: None,
            })
        }
        Err(e) => Json(DecompileResponse {
            source: "".into(),
            success: false,
            error: Some(format!("Decompilation error: {}", e)),
        }),
    }
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/decompile", post(handle_decompile))
        .route("/health", get(|| async { "OK" }));

    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    println!("🚀 unluac-rs server running on http://{}", addr);
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}
