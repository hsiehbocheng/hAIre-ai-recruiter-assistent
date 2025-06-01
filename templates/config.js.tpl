// 由 Terraform 自動生成，請勿手動修改
window.CONFIG = {
    API_BASE_URL: '${api_gateway_url}',
    CLOUDFRONT_URL: 'https://${cloudfront_url}',
    GENERATED_AT: '${timestamp()}'
};

console.log('✅ 系統配置載入:', window.CONFIG); 