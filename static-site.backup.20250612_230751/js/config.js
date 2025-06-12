// 配置檔案 - 由 Terraform 自動生成或手動更新
window.CONFIG = {
    // API Gateway URL - 將由 Terraform output 自動替換
    API_BASE_URL: "${api_gateway_url}",
    
    // CloudFront URL - 將由 Terraform output 自動替換  
    CLOUDFRONT_URL: "${cloudfront_url}",
    
    // 生成時間戳
    GENERATED_AT: "${generated_at}",
    
    // 版本資訊
    VERSION: "1.0.0"
};

// 如果 URL 尚未被 Terraform 替換，則使用預設值（開發用）
if (window.CONFIG.API_BASE_URL.includes("$${")) {
    console.warn("⚠️ API Gateway URL 尚未配置，使用開發用預設值");
    window.CONFIG.API_BASE_URL = "https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev";
}

if (window.CONFIG.CLOUDFRONT_URL.includes("$${")) {
    console.warn("⚠️ CloudFront URL 尚未配置，使用開發用預設值");
    window.CONFIG.CLOUDFRONT_URL = "https://d34pb6c7ehwsy2.cloudfront.net";
}

console.log("✅ 系統配置載入:", window.CONFIG); 