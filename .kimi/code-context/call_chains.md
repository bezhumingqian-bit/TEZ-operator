# 关键调用链

> 从模块依赖推导出的核心数据流。


## `app.routers.ai`


### → `app.services.ai_service`


## `app.routers.auth`


## `app.routers.contacts`


### → `app.services.contact_service`

- → `app.models.contact`

## `app.routers.hosts`


### → `app.services.export_service`


### → `app.services.host_service`

- → `app.clients.base`
- → `app.clients.cmdb`
- → `app.clients.idcrm`
- → `app.clients.tcum`
- → `app.models.host`
- → `app.services.cache_service` (同级服务)

### → `app.services.zone_resource_service`

- → `app.clients.cmdb`
- → `app.clients.idcrm_http`
- → `app.clients.tcum_browser`
- → `app.clients.tcum_http`
- → `app.models.zone_snapshot`

## `app.routers.knowledge`


### → `app.services.document_parser`


### → `app.services.knowledge_service`

- → `app.models.knowledge`

## `app.routers.op_logs`


## `app.routers.workorders`


### → `app.services.workorder_service`

- → `app.models.contact`
- → `app.models.op_log`
- → `app.models.workorder`