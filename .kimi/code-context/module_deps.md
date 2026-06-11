# 模块依赖关系

> 自动生成，不要手动修改。运行 `python scripts/generate_code_context.py` 更新。


## 入口层

- **`app.main`** → `app`, `app.clients.browser_session`, `app.config`, `app.deps`, `app.routers`, `app.routers.ai`, `app.routers.auth`, `app.routers.contacts`, `app.routers.cost`, `app.routers.hosts`, `app.routers.knowledge`, `app.routers.op_logs`, `app.routers.workorders`, `app.scheduler`, `app.services.cache_service`, `app.services.workorder_service`, `app.utils.logger`

## 路由层

- **`app.routers.ai`** → `app.deps`, `app.models.knowledge`, `app.services.ai_service`
- **`app.routers.auth`** → `app.config`, `app.deps`, `app.models.user`, `app.utils.logger`
- **`app.routers.contacts`** → `app.deps`, `app.schemas.contact`, `app.services.contact_service`
- **`app.routers.cost`**
- **`app.routers.hosts`** → `app.clients.browser_session`, `app.clients.idcrm_http`, `app.clients.tcum_browser`, `app.clients.tcum_http`, `app.config`, `app.deps`, `app.models.zone_snapshot`, `app.schemas.host`, `app.services.export_service`, `app.services.host_service`, `app.services.zone_resource_service`, `app.skills.idcrm_position_skill`, `app.utils.device_classifier`, `app.utils.logger`, `app.utils.parser`
- **`app.routers.knowledge`** → `app.deps`, `app.models.knowledge`, `app.services.document_parser`, `app.services.knowledge_service`
- **`app.routers.op_logs`** → `app.deps`, `app.models.op_log`
- **`app.routers.workorders`** → `app.deps`, `app.services.workorder_service`

## 服务层

- **`app.services.ai_service`** → `app.config`, `app.utils.logger`
- **`app.services.cache_service`** → `app.config`, `app.utils.logger`
- **`app.services.contact_service`** → `app.models.contact`, `app.schemas.contact`, `app.utils.logger`
- **`app.services.document_parser`**
- **`app.services.export_service`** → `app.schemas.host`
- **`app.services.host_service`** → `app.clients.base`, `app.clients.cmdb`, `app.clients.idcrm`, `app.clients.tcum`, `app.config`, `app.deps`, `app.models.host`, `app.schemas.host`, `app.services.cache_service`, `app.utils.alert`, `app.utils.logger`, `app.utils.normalize`
- **`app.services.knowledge_service`** → `app.models.knowledge`, `app.utils.logger`
- **`app.services.workorder_service`** → `app.deps`, `app.models.contact`, `app.models.op_log`, `app.models.workorder`, `app.skills.tencent_doc_skill`, `app.utils.logger`
- **`app.services.zone_resource_service`** → `app.clients.cmdb`, `app.clients.idcrm_http`, `app.clients.tcum_browser`, `app.clients.tcum_http`, `app.config`, `app.models.zone_snapshot`, `app.skills.idcrm_position_skill`, `app.utils.device_classifier`, `app.utils.logger`

## 客户端层

- **`app.clients.base`** → `app.utils.logger`
- **`app.clients.base_browser`** → `app.clients.base`, `app.clients.browser_session`, `app.config`, `app.utils.logger`, `app.utils.normalize`
- **`app.clients.browser_session`** → `app.config`, `app.utils.logger`
- **`app.clients.cmdb`** → `app.clients.base`, `app.clients.cmdb_browser`, `app.clients.cmdb_mock`, `app.config`, `app.utils.logger`
- **`app.clients.cmdb_browser`** → `app.clients.base_browser`, `app.clients.browser_session`, `app.utils.logger`
- **`app.clients.cmdb_mock`**
- **`app.clients.idcrm`** → `app.clients.base`, `app.clients.idcrm_browser`, `app.clients.idcrm_mock`, `app.config`, `app.utils.logger`
- **`app.clients.idcrm_browser`** → `app.clients.base_browser`, `app.clients.browser_session`, `app.utils.logger`
- **`app.clients.idcrm_http`** → `app.clients.browser_session`, `app.config`, `app.utils.logger`
- **`app.clients.idcrm_mock`**
- **`app.clients.tcum`** → `app.clients.base`, `app.clients.tcum_browser`, `app.clients.tcum_mock`, `app.config`, `app.utils.logger`
- **`app.clients.tcum_browser`** → `app.clients.base_browser`, `app.clients.browser_session`, `app.utils.logger`
- **`app.clients.tcum_http`** → `app.clients.browser_session`, `app.config`, `app.utils.logger`
- **`app.clients.tcum_mock`**

## 模型层

- **`app.models.base`**
- **`app.models.contact`** → `app.models.base`
- **`app.models.host`** → `app.models.base`
- **`app.models.knowledge`** → `app.models.base`
- **`app.models.op_log`** → `app.models.base`
- **`app.models.user`** → `app.models.base`
- **`app.models.workorder`** → `app.models.base`
- **`app.models.zone_snapshot`** → `app.models.base`

## 工具层

- **`app.utils.alert`** → `app.config`, `app.utils.logger`
- **`app.utils.device_classifier`**
- **`app.utils.logger`**
- **`app.utils.normalize`** → `app.utils.logger`
- **`app.utils.parser`**

## 其他
