import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  getLicence,
  myLicences,
  myStock,
  searchRegister,
  type RegisterFilters,
} from "../licensing";
import { keys } from "./keys";

export function useMyLicences() {
  return useQuery({ queryKey: keys.myLicences, queryFn: myLicences });
}

export function useMyStock() {
  return useQuery({ queryKey: keys.myStock, queryFn: myStock });
}

export function useRegister(filters: RegisterFilters = {}) {
  return useQuery({
    queryKey: keys.registerSearch(filters),
    queryFn: () => searchRegister(filters),
    placeholderData: keepPreviousData,
  });
}

export function useLicence(id: number) {
  return useQuery({ queryKey: keys.licence(id), queryFn: () => getLicence(id) });
}
