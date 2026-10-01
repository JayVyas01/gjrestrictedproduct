"""The licensee's own stock (the view filters by GSTIN; row-level security enforces it too)."""

from rest_framework.response import Response
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role
from stock.models import StockBalance


class MyStockView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def get(self, request):
        rows = (
            StockBalance.objects.select_related("substance")
            .filter(gstin_index=request.user.licensee_gstin_index)
            .order_by("substance__name")
        )
        return Response(
            [
                {
                    "substance_code": r.substance.code,
                    "substance": r.substance.name,
                    "quantity": str(r.quantity),
                    "unit": r.substance.unit,
                }
                for r in rows
            ]
        )
