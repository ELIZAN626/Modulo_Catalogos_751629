import os
import uuid
import boto3
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, EmailStr, validator

# configuracion mediante variables de entorno (Factor 3)
REGION = os.getenv("AWS_REGION", "us-east-1")
CLIENTES_TABLE = os.getenv("CLIENTES_TABLE", "clientes")
DOMICILIOS_TABLE = os.getenv("DOMICILIOS_TABLE", "domicilios")
PRODUCTOS_TABLE = os.getenv("PRODUCTOS_TABLE", "productos")

app = FastAPI(title="API de Catalogos")

def dynamodb_resource():
    return boto3.resource('dynamodb', region_name=REGION)

def preparar_para_dynamo(data):
    if isinstance(data, dict):
        return {k: preparar_para_dynamo(v) for k, v in data.items()}
    if isinstance(data, list):
        return [preparar_para_dynamo(i) for i in data]
    if isinstance(data, float):
        return Decimal(str(data))
    return data

# metodos base de base de datos
def _put_item(table_name: str, item: Dict[str, Any]):
    table = dynamodb_resource().Table(table_name)
    item_limpio = preparar_para_dynamo(item)
    table.put_item(Item=item_limpio)

def _get_item(table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    table = dynamodb_resource().Table(table_name)
    response = table.get_item(Key=key)
    return response.get('Item')

def _scan_table(table_name: str) -> List[Dict[str, Any]]:
    table = dynamodb_resource().Table(table_name)
    response = table.scan()
    return response.get('Items', [])

def _delete_item(table_name: str, key: Dict[str, Any]):
    table = dynamodb_resource().Table(table_name)
    table.delete_item(Key=key)

# modelos
class ClienteBase(BaseModel):
    razon_social: str
    nombre_comercial: str
    rfc: str
    correo_electronico: EmailStr
    telefono: str

class Cliente(ClienteBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class DomicilioBase(BaseModel):
    id_cliente: str
    calle: str
    numero_exterior: str
    colonia: str
    codigo_postal: str
    municipio: str
    estado: str
    tipo: str

    @validator('tipo')
    def tipo_debe_ser_valido(cls, v):
        if v not in ["FACTURACION", "ENVIO"]:
            raise ValueError('tipo debe ser FACTURACION o ENVIO')
        return v

class Domicilio(DomicilioBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class ProductoBase(BaseModel):
    nombre: str
    unidad_medida: str
    precio_base: float

class Producto(ProductoBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

# endpoints
@app.post("/clientes", status_code=201, response_model=Cliente)
def crear_cliente(cliente: ClienteBase):
    nuevo = Cliente(**cliente.dict())
    _put_item(CLIENTES_TABLE, nuevo.dict())
    return nuevo

@app.get("/clientes", response_model=List[Cliente])
def listar_clientes():
    return _scan_table(CLIENTES_TABLE)

@app.post("/domicilios", status_code=201, response_model=Domicilio)
def crear_domicilio(domicilio: DomicilioBase):
    if not _get_item(CLIENTES_TABLE, {'id': domicilio.id_cliente}):
        raise HTTPException(
            status_code=404,
            detail=f"No existe un cliente con id '{domicilio.id_cliente}'.",
        )
    nuevo = Domicilio(**domicilio.dict())
    _put_item(DOMICILIOS_TABLE, nuevo.dict())
    return nuevo

@app.post("/productos", status_code=201, response_model=Producto)
def crear_producto(producto: ProductoBase):
    nuevo = Producto(**producto.dict())
    _put_item(PRODUCTOS_TABLE, nuevo.dict())
    return nuevo