import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  getLicence,
  myLicences,
  myStock,
  searchRegister,
  type RegisterFilters,
  type RegisterSearch,
} from "../licensing";
import { keys } from "./keys";

export function useMyLicences() {
  return useQuery({ queryKey: keys.myLicences, queryFn: myLicences });
}

export function useMyStock() {
  return useQuery({ queryKey: keys.myStock, queryFn: myStock });
}

/** One page of the register. The search value is kept in memory only (the query cache). */
export function useRegister(filters: RegisterFilters = {}, search: RegisterSearch = {}) {
  return useQuery({
    queryKey: keys.registerSearch(filters, search),
    queryFn: () => searchRegister(filters, search),
    placeholderData: keepPreviousData,
  });
}

export function useLicence(id: number, enabled = true) {
  return useQuery({ queryKey: keys.licence(id), queryFn: () => getLicence(id), enabled });
}
