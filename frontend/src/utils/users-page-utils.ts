interface BuildUsersListEndpointInput {
  page: number;
  search: string;
  role: string;
}

interface RecoverInput {
  requestedPage: number;
  count: number;
  resultsLength: number;
  pageSize: number;
}

interface ResetPageOnFilterChangeInput {
  currentPage: number;
  prevSearch: string;
  nextSearch: string;
  prevRole: string;
  nextRole: string;
}

interface BuildUserWritePayloadInput {
  role: string;
  department: number | null;
}

export interface UserDepartmentOption {
  id: number;
  name: string;
}

export function buildUsersListEndpoint({ page, search, role }: BuildUsersListEndpointInput): string {
  const params = new URLSearchParams();
  params.set('page', String(Math.max(1, page)));

  const normalizedSearch = search.trim();
  const normalizedRole = role.trim();

  if (normalizedSearch) {
    params.set('search', normalizedSearch);
  }
  if (normalizedRole) {
    params.set('role', normalizedRole);
  }

  return `/users/?${params.toString()}`;
}

export function getTotalPages(count: number, pageSize: number): number {
  if (count <= 0) return 1;
  return Math.max(1, Math.ceil(count / pageSize));
}

export function shouldRecoverToLastPage({ requestedPage, count, resultsLength, pageSize }: RecoverInput): boolean {
  if (requestedPage <= 1) return false;
  if (count <= 0) return false;
  if (resultsLength > 0) return false;

  return requestedPage > getTotalPages(count, pageSize);
}

export function resetPageOnFilterChange({
  currentPage,
  prevSearch,
  nextSearch,
  prevRole,
  nextRole,
}: ResetPageOnFilterChangeInput): number {
  const searchChanged = prevSearch !== nextSearch;
  const roleChanged = prevRole !== nextRole;
  return searchChanged || roleChanged ? 1 : currentPage;
}

export function shouldShowDepartmentField(role: string): boolean {
  return role === 't';
}

export function buildUserWritePayload({ role, department }: BuildUserWritePayloadInput): { role: string; department: number | null } {
  return {
    role,
    department: shouldShowDepartmentField(role) ? department : null,
  };
}

export function canOpenExceptionalCases(role: string, isSelf: boolean): boolean {
  return role === 's' && !isSelf;
}

export function resolveDepartmentOptions(items: UserDepartmentOption[]): UserDepartmentOption[] {
  return items;
}
