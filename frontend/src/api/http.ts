/** 网络错误独立于后端业务 warnings；支持取消与超时。 */
export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(15000);
  const signal = init.signal
    ? AbortSignal.any([init.signal, timeout])
    : timeout;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, signal });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new Error(
      timeout.aborted
        ? "请求超时，请稍后重试。"
        : "暂时无法连接服务，请检查网络或后端服务。",
    );
  }
  if (!response.ok) {
    if (response.status === 404)
      throw new Error("未找到这所高校，可能已被更新。");
    if (response.status >= 500) throw new Error("服务暂时不可用，请稍后重试。");
    throw new Error(`请求未完成（HTTP ${response.status}），请检查查询条件。`);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("服务返回的数据无法解析，请重试。");
  }
}
