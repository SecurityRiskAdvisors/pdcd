# Global settings

The following environment variables can be used for fine-tuning internal settings for the tool. Source: `pdcd.settings:GlobalSettings`

|Variable Name|Description|Config Name|Default|
|---|---|---|---|
|PDCD_LOGFILE|Log file path|N/A|.pdcd.log|
|PDCD_CFGDIR|Directory that contains shared configuration settings such as connectors file|N/A|~/.pdcd|
|PDCD_CONNECTORS|Path to Connectors file|connectors_file|PDCD_CFGDIR + "/" + "connectors"|
|PDCD_SMB_SHARE|Share name for remote build server SMB server|smb_share_name|pdcd|
|PDCD_SMB_TARGET|SMB port on remote build server|smb_target_port|445|
|PDCD_SMB_BIND|Local port to bind to for SMB port forward when using remote builds|smb_bind_port|<random high port>|
|PDCD_DOCKER_TARGET|Docker daemon port on remote build server|docker_target_port|2375|
|PDCD_DOCKER_BIND|Local port to bind to for Docker port forward when using remote builds|docker_bind_port|<random high port>|
|PDCD_SHELL_LOGGING|Log external commands execute via `utils.shell()`|shell_logging|True|
|PDCD_MYTHIC_INTERVAL|Callback interval for HTTP/S payloads|mythic_callback_interval|15|
|PDCD_MYTHIC_JITTER|Callback jitter percent|mythic_jitter_percent|30|
|PDCD_MYTHIC_HTTP_GETURI|HTTP/S GET URI|mythic_http_geturi|search|
|PDCD_MYTHIC_HTTP_POSTURI|HTTP/S POST URI|mythic_http_posturi|form|
|PDCD_MYTHIC_HTTP_QUERYURI|HTTP/S query URI|mythic_http_queryuri|query|
|PDCD_MYTHIC_HTTP_UA|HTTP/S user-agent|mythic_http_useragent|Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko|
|PDCD_MYTHIC_SMB_PIPENAME|Override pipe name used for Mythic SMB payloads|mythic_smb_pipename|TSVNCache-00000000487ca41a|
|PDCD_DOCKER_MEM_LIMIT|Max memory for Docker|docker_mem_limit|2G|
|PDCD_DOCKER_MEMSWAP_LIMIT|Max swap for Docker|docker_memswap_limit|2G|

