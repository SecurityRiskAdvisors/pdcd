# Global settings

The following environment variables can be used for fine-tuning internal settings for the tool. Source: `pdcd.settings:GlobalSettings`

|Variable|Description|Default|
|---|---|---|
|PDCD_LOGFILE|Log file path|.pdcd.log|
|PDCD_CFGDIR|Directory that contains shared configuration settings such as connectors file|~/.pdcd|
|PDCD_CONNECTORS|Path to Connectors file|PDCD_CFGDIR + "/" + "connectors"|
|PDCD_SMB_SHARE|Share name for remote build server SMB server|pdcd|
|PDCD_SMB_TARGET|SMB port on remote build server|445|
|PDCD_SMB_BIND|Local port to bind to for SMB port forward when using remote builds|<random high port>|
|PDCD_DOCKER_TARGET|Docker daemon port on remote build server|2375|
|PDCD_DOCKER_BIND|Local port to bind to for Docker port forward when using remote builds|<random high port>|
|PDCD_SHELL_LOGGING|Log external commands execute via `utils.shell()`|True|
|PDCD_MYTHIC_INTERVAL|Callback interval for HTTP/S payloads|15|
|PDCD_MYTHIC_JITTER|Callback jitter percent|30|
|PDCD_MYTHIC_HTTP_GETURI|HTTP/S GET URI|search|
|PDCD_MYTHIC_HTTP_POSTURI|HTTP/S POST URI|form|
|PDCD_MYTHIC_HTTP_QUERYURI|HTTP/S query URI|query|
|PDCD_MYTHIC_HTTP_UA|HTTP/S user-agent|Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko|
|PDCD_MYTHIC_SMB_PIPENAME|Override pipe name used for Mythic SMB payloads|TSVNCache-00000000487ca41a|
|PDCD_DOCKER_MEM_LIMIT|Max memory for Docker|2G|
|PDCD_DOCKER_MEMSWAP_LIMIT|Max swap for Docker|2G|

