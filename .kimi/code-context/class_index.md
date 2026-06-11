# 类索引

> 自动生成，不要手动修改。


## `app.routers.ai`


### `ChatRequest`

**属性:**
- `context_type : str | None`
- `history : list[dict] | None`
- `message : Optional[str]`

### `ChatResponse`

**属性:**
- `model : str`
- `reply : str`
- `usage : dict`

## `app.routers.auth`


### `ChangePasswordRequest`

**属性:**
- `new_password : Optional[str]`
- `old_password : str`

### `LoginRequest`

**属性:**
- `password : str`
- `username : str`

### `LoginResponse`

**属性:**
- `token : str`
- `user : dict`

### `UpdateProfileRequest`

**属性:**
- `display_name : Optional[str]`

### `UserCreate`

**属性:**
- `display_name : str`
- `password : Optional[str]`
- `role : Optional[str]`
- `username : Optional[str]`

### `UserInfo`

**属性:**
- `created_at : datetime | None`
- `display_name : str`
- `id : int`
- `is_active : bool`
- `last_login_at : datetime | None`
- `model_config : dict`
- `permissions : list[str]`
- `role : str`
- `username : str`

### `UserUpdate`

**属性:**
- `display_name : str | None`
- `is_active : bool | None`
- `password : str | None`
- `role : str | None`

## `app.routers.knowledge`


### `ArticleContentResponse`

**属性:**
- `content : str`
- `id : int`
- `source_file : str | None`
- `title : str`

### `ArticleCreate`

**属性:**
- `category : str`
- `content : str | None`
- `importance : int`
- `summary : str | None`
- `tags : str | None`
- `title : str`
- `url : str | None`

### `ArticleInfo`

**属性:**
- `category : str`
- `id : int`
- `importance : int`
- `model_config : dict`
- `summary : str | None`
- `tags : str | None`
- `title : str`
- `url : str | None`

### `FAQCreate`

**属性:**
- `answer : str`
- `category : str | None`
- `question : str`
- `tags : str | None`

### `FAQInfo`

**属性:**
- `answer : str`
- `category : str | None`
- `id : int`
- `model_config : dict`
- `question : str`
- `tags : str | None`

### `LinkCreate`

**属性:**
- `category : str | None`
- `importance : int`
- `name : str`
- `purpose : str | None`
- `url : str`

### `LinkInfo`

**属性:**
- `category : str | None`
- `id : int`
- `importance : int`
- `model_config : dict`
- `name : str`
- `purpose : str | None`
- `url : str`

### `SearchResponse`

**属性:**
- `articles : list[ArticleInfo]`
- `faqs : list[FAQInfo]`
- `links : list[LinkInfo]`
- `query : str`
- `total : int`

## `app.routers.op_logs`


### `OpLogItem`

**属性:**
- `action : str`
- `created_at : datetime | None`
- `detail : dict | None`
- `id : int`
- `message : str | None`
- `model_config : dict`
- `status : str`
- `target : str`
- `workorder_no : str | None`

### `OpLogListResponse`

**属性:**
- `fail_count : int`
- `items : list[OpLogItem]`
- `ok_count : int`
- `total : int`
- `warn_count : int`

## `app.routers.workorders`


### `DemandCreate`

**属性:**
- `appid : Optional[str]`
- `contact : Optional[str]`
- `device_count : Optional[int]`
- `expected_date : Optional[str]`
- `machine_type : Optional[str]`
- `purpose : Optional[str]`
- `remark : Optional[str]`
- `requester : Optional[str]`
- `source_zone : Optional[str]`
- `target_zone : Optional[str]`

### `OrderBrief`

**属性:**
- `assignee : str | None`
- `created_at : datetime | None`
- `creator : str`
- `detail : dict | None`
- `id : int`
- `model_config : dict`
- `order_no : str`
- `order_type : str`
- `priority : int`
- `status : str`
- `title : str`
- `updated_at : datetime | None`

### `OrderCreate`

**属性:**
- `creator : Optional[str]`
- `detail : dict | None`
- `note : str | None`
- `order_type : Optional[str]`
- `priority : Optional[int]`
- `title : Optional[str]`

### `OrderInfo`

**属性:**
- `assignee : str | None`
- `completed_at : datetime | None`
- `created_at : datetime | None`
- `creator : str`
- `detail : dict | None`
- `id : int`
- `logs : list[OrderLogInfo]`
- `model_config : dict`
- `note : str | None`
- `order_no : str`
- `order_type : str`
- `pre_checks : dict | None`
- `priority : int`
- `status : str`
- `title : str`
- `updated_at : datetime | None`

### `OrderListResponse`

**属性:**
- `items : list[OrderBrief]`
- `total : int`

### `OrderLogInfo`

**属性:**
- `action : str`
- `content : str | None`
- `created_at : datetime | None`
- `from_status : str | None`
- `id : int`
- `model_config : dict`
- `operator : str`
- `to_status : str | None`

### `StatsResponse`

**属性:**
- `completed : int`
- `pending : int`
- `processing : int`
- `rejected : int`
- `submitted : int`
- `total : int`
- `verifying : int`

### `TransitionRequest`

**属性:**
- `comment : str | None`
- `operator : Optional[str]`
- `to_status : Optional[str]`

## `app.services.ai_service`


### `AIService`

**属性:**
- `MAX_CONTEXT_PER_DOC : int`
- `MAX_HISTORY_TURNS : int`
- `MAX_TOTAL_CONTEXT : int`
- `is_configured`
**方法:**
- `analyze_competitive(documents_content: str, question: str) -> dict[str, Any]`
- `answer_ops_question(question: str, knowledge_context: str) -> dict[str, Any]`
- `chat(user_message: str, context: str | None, context_type: str | None, history: list[dict] | None) -> dict[str, Any]`

## `app.services.cache_service`


### `CacheService`

**方法:**
- `close() -> None`
- `delete(key: str) -> None`
- `get(key: str) -> Any`
- `set(key: str, value: Any, ttl: int | None) -> None`

### `_MemoryCache`

**方法:**
- `clear() -> None`
- `delete(key: str) -> None`
- `get(key: str) -> str | None`
- `set(key: str, value: str, ttl: int) -> None`

## `app.services.contact_service`


### `ContactService`

**属性:**
- `session : AsyncSession`
**方法:**
- `assign_responsibility(contact_id: int, category_id: int, priority: int, note: str | None) -> Responsibility`
- `create_category(name: str, parent_id: int | None, description: str | None) -> Category`
- `create_contact(data: ContactCreate) -> Contact`
- `get_contact(contact_id: int) -> Contact | None`
- `get_contact_by_name(name: str) -> Contact | None`
- `list_categories() -> list[Category]`
- `list_contacts(status: str | None) -> list[Contact]`
- `route(query: str) -> list[RouteResult]`
- `search_contacts(keyword: str) -> list[Contact]`
- `update_contact(contact_id: int, data: ContactUpdate) -> Contact | None`

## `app.services.host_service`


### `HostService`

**属性:**
- `DB_EXPIRE_DAYS : int`
- `cache`
- `cmdb`
- `idcrm`
- `tcum`
**方法:**
- `batch_get_hosts(asset_ids: list[str]) -> list[tuple[str, HostInfo | None, str | None]]`
- `batch_get_hosts_mixed(queries: list[tuple[str, str]]) -> list[tuple[str, str, HostInfo | None, str | None]]`
- `close() -> None`
- `get_host(asset_id: str) -> HostInfo | None`
- `get_host_by_ip(ip: str) -> HostInfo | None`
- `get_zone_instance_stats(zones: list[str]) -> list[ZoneInstanceStat]`
- `list_zone_hosts(zone: str) -> list[HostInfo]`
- `list_zones() -> list[str]`

## `app.services.knowledge_service`


### `KnowledgeService`

**属性:**
- `session : AsyncSession`
**方法:**
- `create_article() -> KnowledgeArticle`
- `create_faq() -> FAQ`
- `create_link() -> PlatformLink`
- `list_articles(category: str | None) -> list[KnowledgeArticle]`
- `list_faqs(category: str | None) -> list[FAQ]`
- `list_links() -> list[PlatformLink]`
- `search(query: str) -> dict`

## `app.services.workorder_service`


### `WorkOrderService`

**属性:**
- `session : AsyncSession`
**方法:**
- `create_demand(requester: str, contact: str, title: str, detail: dict[str, Any]) -> WorkOrder`
- `create_order(order_type: str, title: str, creator: str, detail: dict[str, Any] | None, note: str | None, priority: int) -> WorkOrder`
- `get_order(order_id: int) -> WorkOrder | None`
- `get_order_by_no(order_no: str) -> WorkOrder | None`
- `get_stats() -> dict[str, int]`
- `list_orders(status: str | None, order_type: str | None, creator: str | None, assignee: str | None, limit: int, offset: int) -> tuple[list[WorkOrder], int]`
- `retry_pending_pushes() -> int`
- `transition(order_id: int, to_status: str, operator: str, comment: str | None) -> WorkOrder`

## `app.services.zone_resource_service`


### `ZoneResourceService`

**方法:**
- `force_sync(zone: str) -> dict[str, Any]`
- `get_zone_overview(zone: str, force_refresh: bool) -> dict[str, Any]`
- `list_all_snapshots() -> list[dict[str, Any]]`

## `app.clients.base`


### `BaseHTTPClient`

**属性:**
- `base_url`
- `max_retries : int`
- `name : ClassVar[str]`
- `timeout : float`
**方法:**
- `close() -> None`
- `request(method: str, path: str) -> dict[str, Any]`

### `<color:red>BrowserAuthExpired</color>`


### `<color:red>ClientError</color>`


## `app.clients.base_browser`


### `BaseBrowserImpl`

**属性:**
- `DEFAULT_WAIT_AFTER_GOTO_MS : int`
- `SELECTOR_FALLBACKS : tuple[str, ...]`
**方法:**
- `close() -> None`

## `app.clients.browser_session`


### `BrowserSession`

**方法:**
- `close() -> None`
- `is_login_valid() -> bool`
- `page() -> AsyncIterator`
- `profile_exists() -> bool`

## `app.clients.cmdb`


### `CMDBAPIImpl`

**属性:**
- `{abstract`
**方法:**
- `close() -> None`

### `CMDBBrowserImplPlaceholder`

**属性:**
- `{abstract`
**方法:**
- `close() -> None`

### `CMDBClient`

**属性:**
- `mode : Literal`
- `name : str`
**方法:**
- `close() -> None`
- `get_by_asset(asset_id: str) -> dict[str, Any] | None`
- `get_by_ip(ip: str) -> dict[str, Any] | None`
- `get_instance_stats_by_zone(zone: str) -> dict[str, Any]`
- `list_by_zone(zone: str, limit: int) -> list[dict[str, Any]]`

## `app.clients.cmdb_browser`


### `CMDBBrowserImpl`

**属性:**
- `COL_APP_ID : int`
- `COL_ASSET_ID : int`
- `COL_BACKUP_OWNERS : int`
- `COL_CABINET : int`
- `COL_CUSTOMER : int`
- `COL_HAS_TPC : int`
- `COL_IDC : int`
- `COL_IP : int`
- `COL_MACHINE_TYPE : int`
- `COL_MODULE : int`
- `COL_OWNER : int`
- `COL_STATUS : int`
- `COL_ZONE : int`
- `name : str`
- `{abstract`
**方法:**
- `get_by_asset(asset_id: str) -> dict[str, Any] | None`
- `get_by_ip(ip: str) -> dict[str, Any] | None`

## `app.clients.cmdb_mock`


### `CMDBMockImpl`

**属性:**
- `name : str`
**方法:**
- `close() -> None`
- `get_by_asset(asset_id: str) -> dict[str, Any] | None`
- `get_by_ip(ip: str) -> dict[str, Any] | None`
- `get_instance_stats_by_zone(zone: str) -> dict[str, Any]`
- `list_by_zone(zone: str, limit: int) -> list[dict[str, Any]]`

## `app.clients.idcrm`


### `IDCRMAPIImpl`

**属性:**
- `{abstract`
**方法:**
- `close() -> None`

### `IDCRMClient`

**属性:**
- `mode : Literal`
- `name : str`
**方法:**
- `close() -> None`
- `get_position(idc: str, cabinet: str | None, asset_id: str | None) -> dict[str, Any] | None`

## `app.clients.idcrm_browser`


### `IDCRMBrowserImpl`

**属性:**
- `COL_CABINET : int`
- `COL_HAS_TPC : int`
- `COL_IDC : int`
- `COL_POSITION : int`
- `COL_STATUS : int`
- `name : str`
**方法:**
- `get_position(idc: str, cabinet: str | None, asset_id: str | None) -> dict[str, Any] | None`

## `app.clients.idcrm_http`


### `IDCRMHttpClient`

**属性:**
- `LOGIN_WAIT_TIMEOUT : int`
**方法:**
- `query_all_positions() -> dict[str, Any]`
- `query_positions(page, idc_unit_name: str | None, logic_area_attr: str | None, page_no: int, page_size: int) -> dict[str, Any]`
- `query_positions_by_idc(idc: str) -> dict[str, Any]`

## `app.clients.idcrm_mock`


### `IDCRMMockImpl`

**属性:**
- `name : str`
**方法:**
- `close() -> None`
- `get_position(idc: str, cabinet: str | None, asset_id: str | None) -> dict[str, Any] | None`

## `app.clients.tcum`


### `TCUMAPIImpl`

**属性:**
- `name : str`
- `{abstract`
**方法:**
- `close() -> None`

### `TCUMClient`

**属性:**
- `mode : Literal`
- `name : str`
**方法:**
- `close() -> None`
- `get_by_asset(asset_id: str) -> dict[str, Any] | None`
- `search_by_ip(ip: str) -> dict[str, Any] | None`

## `app.clients.tcum_browser`


### `TCUMBrowserImpl`

**属性:**
- `name : str`
**方法:**
- `batch_search(asset_ids: list[str]) -> list[dict[str, Any]]`
- `get_by_asset(asset_id: str) -> dict[str, Any] | None`
- `search_by_ip(ip: str) -> dict[str, Any] | None`

## `app.clients.tcum_http`


### `TCUMHttpClient`

**属性:**
- `CMDB_API_BASE : str`
- `LOGIN_WAIT_TIMEOUT : int`
**方法:**
- `batch_search(asset_ids: list[str]) -> list[dict[str, Any]]`
- `search_single(asset_id: str) -> dict[str, Any] | None`

## `app.clients.tcum_mock`


### `TCUMMockImpl`

**属性:**
- `name : str`
**方法:**
- `close() -> None`
- `get_by_asset(asset_id: str) -> dict[str, Any] | None`
- `search_by_ip(ip: str) -> dict[str, Any] | None`

## `app.models.base`


### `Base`

**属性:**
- `metadata : MetaData`

### `TimestampMixin`

**属性:**
- `created_at : Mapped[datetime]`
- `updated_at : Mapped[datetime]`

## `app.models.contact`


### `Category`

**属性:**
- `created_at : Mapped[datetime]`
- `description : Mapped[Optional[str]]`
- `id : Mapped[int]`
- `name : Mapped[str]`
- `parent : Mapped[Optional['Category']]`
- `parent_id : Mapped[Optional[int]]`
- `responsibilities : Mapped[list['Responsibility']]`
- `sort_order : Mapped[int]`

### `Contact`

**属性:**
- `created_at : Mapped[datetime]`
- `display_name : Mapped[Optional[str]]`
- `id : Mapped[int]`
- `name : Mapped[str]`
- `note : Mapped[Optional[str]]`
- `phone : Mapped[Optional[str]]`
- `responsibilities : Mapped[list['Responsibility']]`
- `role : Mapped[Optional[str]]`
- `status : Mapped[str]`
- `team : Mapped[Optional[str]]`
- `updated_at : Mapped[datetime]`
- `wecom_id : Mapped[Optional[str]]`

### `EscalationPath`

**属性:**
- `category : Mapped['Category']`
- `category_id : Mapped[int]`
- `contact : Mapped['Contact']`
- `contact_id : Mapped[int]`
- `description : Mapped[Optional[str]]`
- `id : Mapped[int]`
- `level : Mapped[int]`

### `Responsibility`

**属性:**
- `category : Mapped['Category']`
- `category_id : Mapped[int]`
- `contact : Mapped['Contact']`
- `contact_id : Mapped[int]`
- `id : Mapped[int]`
- `note : Mapped[Optional[str]]`
- `priority : Mapped[int]`

## `app.models.host`


### `AuditLog`

**属性:**
- `action : Mapped[str]`
- `created_at : Mapped[datetime]`
- `id : Mapped[int]`
- `ip : Mapped[Optional[str]]`
- `payload : Mapped[Optional[dict]]`
- `user_id : Mapped[Optional[str]]`

### `HostCache`

**属性:**
- `app_id : Mapped[Optional[str]]`
- `asset_id : Mapped[str]`
- `cabinet : Mapped[Optional[str]]`
- `customer : Mapped[Optional[str]]`
- `has_tpc : Mapped[Optional[bool]]`
- `idc : Mapped[Optional[str]]`
- `ip : Mapped[Optional[str]]`
- `last_sync_at : Mapped[Optional[datetime]]`
- `machine_type : Mapped[Optional[str]]`
- `module : Mapped[Optional[str]]`
- `position : Mapped[Optional[str]]`
- `raw_json : Mapped[Optional[dict]]`
- `status : Mapped[Optional[str]]`
- `zone : Mapped[Optional[str]]`

### `HostHistory`

**属性:**
- `asset_id : Mapped[str]`
- `created_at : Mapped[datetime]`
- `description : Mapped[Optional[str]]`
- `event_at : Mapped[datetime]`
- `event_type : Mapped[str]`
- `from_module : Mapped[Optional[str]]`
- `id : Mapped[int]`
- `source : Mapped[Optional[str]]`
- `to_module : Mapped[Optional[str]]`

## `app.models.knowledge`


### `FAQ`

**属性:**
- `answer : Mapped[str]`
- `category : Mapped[Optional[str]]`
- `created_at : Mapped[datetime]`
- `id : Mapped[int]`
- `question : Mapped[str]`
- `sort_order : Mapped[int]`
- `status : Mapped[str]`
- `tags : Mapped[Optional[str]]`
- `updated_at : Mapped[datetime]`

### `KnowledgeArticle`

**属性:**
- `category : Mapped[str]`
- `content : Mapped[Optional[str]]`
- `created_at : Mapped[datetime]`
- `id : Mapped[int]`
- `importance : Mapped[int]`
- `source_file : Mapped[Optional[str]]`
- `status : Mapped[str]`
- `summary : Mapped[Optional[str]]`
- `tags : Mapped[Optional[str]]`
- `title : Mapped[str]`
- `updated_at : Mapped[datetime]`
- `url : Mapped[Optional[str]]`

### `PlatformLink`

**属性:**
- `category : Mapped[Optional[str]]`
- `created_at : Mapped[datetime]`
- `id : Mapped[int]`
- `importance : Mapped[int]`
- `name : Mapped[str]`
- `purpose : Mapped[Optional[str]]`
- `status : Mapped[str]`
- `url : Mapped[str]`

## `app.models.op_log`


### `OperationLog`

**属性:**
- `action : Mapped[str]`
- `created_at : Mapped[datetime]`
- `detail : Mapped[Optional[dict]]`
- `id : Mapped[int]`
- `message : Mapped[Optional[str]]`
- `status : Mapped[str]`
- `target : Mapped[str]`
- `workorder_no : Mapped[Optional[str]]`

## `app.models.user`


### `User`

**属性:**
- `created_at : Mapped[Optional[datetime]]`
- `display_name : Mapped[str]`
- `id : Mapped[int]`
- `is_active : Mapped[bool]`
- `last_login_at : Mapped[Optional[datetime]]`
- `password_hash : Mapped[str]`
- `role : Mapped[str]`
- `username : Mapped[str]`

## `app.models.workorder`


### `WorkOrder`

**属性:**
- `assignee : Mapped[Optional[str]]`
- `completed_at : Mapped[Optional[datetime]]`
- `created_at : Mapped[datetime]`
- `creator : Mapped[str]`
- `detail : Mapped[Optional[dict]]`
- `id : Mapped[int]`
- `logs : Mapped[list['WorkOrderLog']]`
- `note : Mapped[Optional[str]]`
- `order_no : Mapped[str]`
- `order_type : Mapped[str]`
- `pre_checks : Mapped[Optional[dict]]`
- `priority : Mapped[int]`
- `status : Mapped[str]`
- `title : Mapped[str]`
- `updated_at : Mapped[datetime]`

### `WorkOrderLog`

**属性:**
- `action : Mapped[str]`
- `content : Mapped[Optional[str]]`
- `created_at : Mapped[datetime]`
- `from_status : Mapped[Optional[str]]`
- `id : Mapped[int]`
- `operator : Mapped[str]`
- `order_id : Mapped[int]`
- `to_status : Mapped[Optional[str]]`
- `work_order : Mapped['WorkOrder']`

## `app.models.zone_snapshot`


### `ZoneDevice`

**属性:**
- `asset_id : Mapped[str]`
- `category : Mapped[Optional[str]]`
- `id : Mapped[int]`
- `ip : Mapped[Optional[str]]`
- `is_tez : Mapped[bool]`
- `machine_type : Mapped[Optional[str]]`
- `module : Mapped[Optional[str]]`
- `reason : Mapped[Optional[str]]`
- `status : Mapped[Optional[str]]`
- `zone : Mapped[str]`

### `ZoneSnapshot`

**属性:**
- `free_count : Mapped[int]`
- `idc : Mapped[Optional[str]]`
- `last_sync_at : Mapped[Optional[datetime]]`
- `non_tez_count : Mapped[int]`
- `offline_count : Mapped[int]`
- `online_count : Mapped[int]`
- `other_count : Mapped[int]`
- `raw_data : Mapped[Optional[dict]]`
- `total_assets : Mapped[int]`
- `total_positions : Mapped[int]`
- `used_count : Mapped[int]`
- `zone : Mapped[str]`

## `app.schemas.common`


### `APIResponse`

**属性:**
- `code : Optional[int]`
- `data : T | None`
- `message : Optional[str]`

### `ErrorResponse`

**属性:**
- `code : int`
- `detail : str | None`
- `message : str`

## `app.schemas.contact`


### `CategoryBase`

**属性:**
- `description : str | None`
- `name : Optional[str]`
- `parent_id : int | None`
- `sort_order : int`

### `CategoryCreate`


### `CategoryInfo`

**属性:**
- `id : int`
- `model_config : dict`

### `ContactBase`

**属性:**
- `display_name : str | None`
- `name : Optional[str]`
- `note : str | None`
- `phone : str | None`
- `role : str | None`
- `status : Literal['active', 'vacation', 'left']`
- `team : str | None`
- `wecom_id : str | None`

### `ContactCreate`


### `ContactInfo`

**属性:**
- `created_at : datetime`
- `id : int`
- `model_config : dict`
- `updated_at : datetime`

### `ContactSearchResponse`

**属性:**
- `contacts : list[ContactInfo]`
- `query : str`
- `total : int`

### `ContactUpdate`

**属性:**
- `display_name : str | None`
- `note : str | None`
- `phone : str | None`
- `role : str | None`
- `status : Literal['active', 'vacation', 'left'] | None`
- `team : str | None`
- `wecom_id : str | None`

### `ResponsibilityInfo`

**属性:**
- `category_id : int`
- `contact`
- `id : int`
- `model_config : dict`
- `note : str | None`
- `priority : Optional[int]`

### `RouteResponse`

**属性:**
- `query : str`
- `results : list[RouteResult]`
- `total : int`

### `RouteResult`

**属性:**
- `backup : Optional[list[ContactInfo]]`
- `category : Optional[str]`
- `escalation : Optional[list[ContactInfo]]`
- `note : str | None`
- `primary : Optional[list[ContactInfo]]`

## `app.schemas.host`


### `BatchSearchItem`

**属性:**
- `data : HostInfo | None`
- `error : str | None`
- `query : str`
- `query_type : Literal['asset_id', 'ip', 'zone', 'unknown']`
- `success : bool`

### `BatchSearchRequest`

**属性:**
- `queries : Optional[list[str]]`

### `BatchSearchResponse`

**属性:**
- `code : int`
- `items : list[BatchSearchItem]`
- `message : str`
- `success_count : int`
- `total : int`

### `HostHistoryEvent`

**属性:**
- `description : str | None`
- `event_at : datetime`
- `event_type : Optional[str]`
- `from_module : str | None`
- `model_config`
- `source : str | None`
- `to_module : str | None`

### `HostInfo`

**属性:**
- `app_id : str | None`
- `asset_id : Optional[str]`
- `backup_owners : Optional[list[str]]`
- `billing_tags : Optional[dict[str, str]]`
- `cabinet : str | None`
- `city : str | None`
- `customer : str | None`
- `has_tpc : bool | None`
- `history : Optional[list[HostHistoryEvent]]`
- `idc : str | None`
- `ip : str | None`
- `machine_type : str | None`
- `meta : Optional[HostMeta]`
- `model_config`
- `module : str | None`
- `owner : str | None`
- `position : str | None`
- `raw_json : dict[str, Any] | None`
- `server_type : str | None`
- `status : HostStatus | None`
- `use_years : float | None`
- `zone : str | None`

### `HostMeta`

**属性:**
- `data_sources : Optional[list[str]]`
- `errors : Optional[dict[str, str]]`
- `from_cache : bool`
- `last_sync_at : datetime | None`
- `partial : Optional[bool]`

### `SearchResponse`

**属性:**
- `code : int`
- `data : HostInfo | list[HostInfo] | None`
- `message : str`
- `query_type : Literal['asset_id', 'ip', 'zone', 'unknown']`

### `ZoneHostsResponse`

**属性:**
- `code : int`
- `items : list[HostInfo]`
- `message : str`
- `total : int`
- `zone : str`

### `ZoneInstanceStat`

**属性:**
- `by_customer : Optional[dict[str, int]]`
- `by_machine_type : Optional[dict[str, int]]`
- `host_count : Optional[int]`
- `maintenance_instances : Optional[int]`
- `offline_instances : Optional[int]`
- `online_instances : Optional[int]`
- `total_instances : Optional[int]`
- `zone : str`

### `ZoneInstanceStatsResponse`

**属性:**
- `code : int`
- `items : list[ZoneInstanceStat]`
- `message : str`
- `online_instances : int`
- `total_hosts : int`
- `total_instances : int`
- `total_zones : int`

## `app.utils.device_classifier`


### `DeviceClassification`

**属性:**
- `is_tez : bool`
- `is_transitional : bool`
- `reason : str | None`

## `app.utils.parser`


### `_ZoneRECompat`

**方法:**
- `match(s: str)`

## `app.config`


### `Settings`

**属性:**
- `ai_api_base : Optional[str]`
- `ai_api_key : Optional[str]`
- `ai_max_tokens : Optional[int]`
- `ai_model : Optional[str]`
- `app_debug : Optional[bool]`
- `app_env : Optional[str]`
- `app_host : Optional[str]`
- `app_log_level : Optional[str]`
- `app_port : Optional[int]`
- `batch_concurrency : Optional[int]`
- `batch_max_size : Optional[int]`
- `browser_headless : Optional[bool]`
- `browser_ignore_https_errors : Optional[bool]`
- `browser_login_valid_days : Optional[int]`
- `browser_page_timeout_ms : Optional[int]`
- `browser_profile_dir : Optional[str]`
- `cache_default_ttl : Optional[int]`
- `cache_zone_ttl : Optional[int]`
- `cmdb_base_url : Optional[str]`
- `cmdb_caller : Optional[str]`
- `cmdb_db_host : Optional[str]`
- `cmdb_db_name : Optional[str]`
- `cmdb_db_password : Optional[str]`
- `cmdb_db_port : Optional[int]`
- `cmdb_db_user : Optional[str]`
- `cmdb_mode : Optional[ClientMode]`
- `cmdb_timeout : Optional[float]`
- `cmdb_token : Optional[str]`
- `database_url : Optional[str]`
- `idcrm_base_url : Optional[str]`
- `idcrm_mode : Optional[ClientMode]`
- `idcrm_timeout : Optional[float]`
- `idcrm_token : Optional[str]`
- `jwt_secret_key : Optional[str]`
- `model_config`
- `password_salt : Optional[str]`
- `redis_url : Optional[str]`
- `tcum_base_url : Optional[str]`
- `tcum_mode : Optional[ClientMode]`
- `tcum_timeout : Optional[float]`
- `tcum_token : Optional[str]`
- `tencent_doc_url : Optional[str]`
- `wecom_webhook : Optional[str]`

## `app.skills.idcrm_position_skill`


### `IDCRMPositionSkill`

**属性:**
- `IDX_IDC_UNIT : int`
- `IDX_LOGIC_AREA : int`
- `IDX_STATUS : int`
- `LOGIC_AREA_VALUE : str`
- `MAX_RETRY : int`
- `STATUS_VALUE : str`
- `WAIT_AFTER_FILTER : int`
- `WAIT_AFTER_GOTO : int`
**方法:**
- `query_all_positions() -> dict[str, Any]`
- `query_free_positions(idc: str) -> dict[str, Any]`

## `app.skills.tencent_doc_skill`


### `TencentDocSkill`

**属性:**
- `WAIT_AFTER_GOTO : int`
- `WAIT_AFTER_INPUT : float`
- `WAIT_AFTER_NAVIGATE : int`
- `WAIT_AFTER_SWITCH_TAB : int`
**方法:**
- `append_deployment_record(data: dict[str, str]) -> dict[str, Any]`
- `append_migration_record(data: dict[str, str]) -> dict[str, Any]`

## `app.skills.ui_skill`


### `UiSkill`

**属性:**
- `LOGIN_TIMEOUT : int`
- `WAIT_AFTER_GOTO : int`
- `WAIT_AFTER_INPUT : float`
- `WAIT_TABLE_LOAD : int`
**方法:**
- `ant_select_direct(page, index: int, exact_match: str) -> bool`
- `ant_select_search(page, index: int, search_text: str, exact_match: str) -> bool`
- `click_expand(page) -> bool`
- `click_with_fallback(page, selectors: list[str]) -> bool`
- `dismiss_overlays(page) -> None`
- `extract_all_pages(page, max_pages: int) -> list[list[str]]`
- `extract_table(page) -> list[list[str]]`
- `fill_input_by_label(page, label_text: str, value: str) -> bool`
- `fill_input_by_placeholder(page, placeholder: str, value: str) -> bool`
- `open_page(url: str) -> Any`
- `retry(func) -> Any`
- `set_page_size(page, size_text: str) -> bool`
- `take_screenshot(page, name: str) -> Optional[str]`
- `wait_table_rows(page, timeout: int) -> int`